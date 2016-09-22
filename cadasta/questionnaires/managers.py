import itertools
import re

from django.apps import apps
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.db import models, transaction
from django.utils.translation import ugettext as _
from jsonattrs.models import Attribute, AttributeType, Schema
from pyxform.builder import create_survey_element_from_dict
from pyxform.errors import PyXFormError
from pyxform.xls2json import parse_file_to_json
from questionnaires.exceptions import InvalidXLSForm

ATTRIBUTE_GROUPS = settings.ATTRIBUTE_GROUPS


def create_children(children, errors=[], project=None, kwargs={}):
    if children:
        for c in children:
            if c.get('type') == 'repeat':
                create_children(c['children'], errors, project, kwargs)
            elif c.get('type') == 'group':
                model_name = 'QuestionGroup'

                # parse attribute group
                attribute_group = c.get('name')
                for attr_group in ATTRIBUTE_GROUPS.keys():
                    if attribute_group.startswith(attr_group):
                        app_label = ATTRIBUTE_GROUPS[attr_group]['app_label']
                        model = ATTRIBUTE_GROUPS[attr_group]['model']
                        content_type = ContentType.objects.get(
                            app_label=app_label, model=model)
                        create_attrs_schema(
                            project=project, dict=c,
                            content_type=content_type, errors=errors
                        )
            else:
                model_name = 'Question'

            if c.get('type') != 'repeat':
                model = apps.get_model('questionnaires', model_name)
                model.objects.create_from_dict(dict=c, errors=errors, **kwargs)


def create_options(options, question, errors=[]):
    if options:
        for o, idx in zip(options, itertools.count()):
            QuestionOption = apps.get_model('questionnaires', 'QuestionOption')

            QuestionOption.objects.create(question=question, index=idx+1, **o)
    else:
        errors.append(_("Please provide at least one option for field"
                        " '{field_name}'".format(field_name=question.name)))


def create_attrs_schema(project=None, dict=None, content_type=None, errors=[]):
    fields = []
    selectors = (project.organization.pk, project.pk,
                 project.current_questionnaire)
    # check if the attribute group has a relevant bind statement,
    # eg ${party_type}='IN'
    # this enables conditional attribute schema creation
    bind = dict.get('bind', None)
    if bind:
        relevant = bind.get('relevant', None)
        if relevant:
            clauses = relevant.split('=')
            selector = re.sub("'", '', clauses[1])
            selectors += (selector,)

    schema_obj = Schema.objects.create(content_type=content_type,
                                       selectors=selectors)

    for c in dict.get('children'):
        field = {}
        field['name'] = c.get('name')
        field['long_name'] = c.get('label')
        # HACK: pyxform renames select_multiple to select all that apply
        if c.get('type') == 'select all that apply':
            field['attr_type'] = 'select_multiple'
        else:
            # HACK: pyxform strips underscores from xform field names
            field['attr_type'] = c.get('type').replace(' ', '_')
        if c.get('default'):
            field['default'] = c.get('default', '')
        if c.get('omit'):
            field['omit'] = c.get('omit')
        bind = c.get('bind')
        if bind:
            field['required'] = True if bind.get(
                'required', 'no') == 'yes' else False
        if c.get('choices'):
            field['choices'] = [choice.get('name')
                                for choice in c.get('choices')]
            field['choice_labels'] = [choice.get('label')
                                      for choice in c.get('choices')]
        fields.append(field)

    for field, index in zip(fields, itertools.count(1)):
        long_name = field.get('long_name', field['name'])
        attr_type = AttributeType.objects.get(name=field['attr_type'])
        choices = field.get('choices', [])
        choice_labels = field.get('choice_labels', None)
        default = field.get('default', '')
        required = field.get('required', False)
        omit = True if field.get('omit', '') == 'yes' else False
        Attribute.objects.create(
            schema=schema_obj,
            name=field['name'], long_name=long_name,
            attr_type=attr_type, index=index,
            choices=choices, choice_labels=choice_labels,
            default=default, required=required, omit=omit
        )


class QuestionnaireManager(models.Manager):

    def create_from_form(self, xls_form=None, original_file=None,
                         project=None):
        try:
            with transaction.atomic():
                errors = []
                instance = self.model(
                    xls_form=xls_form,
                    original_file=original_file,
                    project=project
                )
                json = parse_file_to_json(instance.xls_form.file.name)
                instance.filename = json.get('name')
                instance.title = json.get('title')
                instance.id_string = json.get('id_string')

                # TODO: This needs to go, error handling needs to be changed
                # again
                survey = create_survey_element_from_dict(json)
                survey.xml().toxml()
                # insert version attr into the xform instance root node
                # xml = self.insert_version_attribute(
                #     xml_form, instance.filename, instance.version
                # )
                # name = os.path.join(instance.xml_form.field.upload_to,
                #                     os.path.basename(instance.filename))
                # url = instance.xml_form.storage.save(
                #     '{}.xml'.format(name), xml)
                # instance.xml_form = url

                instance.save()

                project.current_questionnaire = instance.id
                project.save()

                create_children(
                    children=json.get('children'),
                    errors=errors,
                    project=project,
                    kwargs={'questionnaire': instance}
                )

                # all these errors handled by PyXForm so turning off for now
                # if errors:
                #     raise InvalidXLSForm(errors)

                return instance

        except PyXFormError as e:
            raise InvalidXLSForm([str(e)])


class QuestionGroupManager(models.Manager):

    def create_from_dict(self, dict=None, questionnaire=None, errors=[]):
        instance = self.model(questionnaire=questionnaire)

        instance.name = dict.get('name')
        instance.label = dict.get('label')

        instance.save()

        create_children(
            children=dict.get('children'),
            errors=errors,
            project=questionnaire.project,
            kwargs={
                'questionnaire': questionnaire,
                'question_group': instance
            }
        )

        return instance


class QuestionManager(models.Manager):

    def create_from_dict(self, errors=[], **kwargs):
        dict = kwargs.pop('dict')
        instance = self.model(**kwargs)
        type_dict = {name: code for code, name in instance.TYPE_CHOICES}

        relevant = None
        required = False
        bind = dict.get('bind')
        if bind:
            relevant = bind.get('relevant', None)
            required = True if bind.get('required', 'no') == 'yes' else False

        instance.type = type_dict[dict.get('type')]
        instance.name = dict.get('name')
        instance.label = dict.get('label')
        instance.required = required
        instance.constraint = dict.get('constraint')
        instance.default = dict.get('default', None)
        instance.hint = dict.get('hint', None)
        instance.relevant = relevant
        instance.save()

        if instance.has_options:
            create_options(dict.get('choices'), instance, errors=errors)

        return instance
