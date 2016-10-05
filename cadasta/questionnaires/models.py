from buckets.fields import S3FileField
from core.models import RandomIDModel
from django.db import models
from django.utils.translation import ugettext as _
from django.utils.translation import get_language
from django.contrib.postgres.fields import JSONField
from simple_history.models import HistoricalRecords
from tutelary.decorators import permissioned_model

from . import managers, messages


class MultilingualLabelsMixin:
    @property
    def default_language(self):
        if not hasattr(self, '_default_language'):
            if hasattr(self, 'questionnaire'):
                q = self.questionnaire
            else:
                q = self.get_questionnaire()
            self._default_language = q.default_language
        return self._default_language

    @property
    def label(self):
        if isinstance(self.label_or_translations, dict):
            return self.label_or_translations.get(
                get_language(),
                self.label_or_translations[self.default_language]
            )
        else:
            return self.label_or_translations

    @label.setter
    def label(self, value):
        self.label_or_translations = value


@permissioned_model
class Questionnaire(RandomIDModel):
    filename = models.CharField(max_length=100)
    title = models.CharField(max_length=500)
    id_string = models.CharField(max_length=50)
    default_language = models.CharField(max_length=3, null=True)
    xls_form = S3FileField(upload_to='xls-forms')
    xml_form = S3FileField(upload_to='xml-forms', default=False)
    original_file = models.CharField(max_length=200, null=True)
    project = models.ForeignKey('organization.Project',
                                related_name='questionnaires')
    version = models.BigIntegerField(default=1)
    md5_hash = models.CharField(max_length=50, default=False)

    objects = managers.QuestionnaireManager()
    history = HistoricalRecords()

    class Meta:
        unique_together = ('project', 'id_string', 'version')

    class TutelaryMeta:
        perm_type = 'questionnaire'
        path_fields = ('project', 'pk')
        actions = (
            ('questionnaire.view',
             {'description': _("View the questionnaire of the project"),
              'error_message': messages.QUESTIONNAIRE_VIEW,
              'permissions_object': 'project'}),
            ('questionnaire.add',
             {'description': _("Add a questionnaire to the project"),
              'error_message': messages.QUESTIONNAIRE_ADD,
              'permissions_object': 'project'}),
            ('questionnaire.edit',
             {'description': _("Edit an existing questionnaire"),
              'error_message': messages.QUESTIONNAIRE_EDIT,
              'permissions_object': 'project'}),
        )


class QuestionGroup(MultilingualLabelsMixin, RandomIDModel):
    name = models.CharField(max_length=100)
    label = models.CharField(max_length=2500, null=True, blank=True)
    label_or_translations = JSONField()
    questionnaire = models.ForeignKey(Questionnaire,
                                      related_name='question_groups')

    objects = managers.QuestionGroupManager()

    history = HistoricalRecords()


class Question(MultilingualLabelsMixin, RandomIDModel):
    TYPE_CHOICES = (('IN', 'integer'),
                    ('DE', 'decimal'),
                    ('TX', 'text'),
                    ('S1', 'select one'),
                    ('SM', 'select all that apply'),
                    ('NO', 'note'),
                    ('GP', 'geopoint'),
                    ('GT', 'geotrace'),
                    ('GS', 'geoshape'),
                    ('DA', 'date'),
                    ('TI', 'time'),
                    ('DT', 'dateTime'),
                    ('CA', 'calculate'),
                    ('AC', 'acknowledge'),
                    ('PH', 'photo'),
                    ('AU', 'audio'),
                    ('VI', 'video'),
                    ('BC', 'barcode'),

                    # Meta data
                    ('ST', 'start'),
                    ('EN', 'end'),
                    ('TD', 'today'),
                    ('DI', 'deviceid'),
                    ('SI', 'subsciberid'),
                    ('SS', 'simserial'),
                    ('PN', 'phonenumber'))

    name = models.CharField(max_length=100)
    label = models.CharField(max_length=2500, null=True, blank=True)
    label_or_translations = JSONField()
    type = models.CharField(max_length=2, choices=TYPE_CHOICES)
    required = models.BooleanField(default=False)
    constraint = models.CharField(max_length=50, null=True, blank=True)
    questionnaire = models.ForeignKey(Questionnaire, related_name='questions')
    question_group = models.ForeignKey(QuestionGroup,
                                       related_name='questions',
                                       null=True)

    objects = managers.QuestionManager()

    history = HistoricalRecords()

    @property
    def has_options(self):
        return self.type in ['S1', 'SM']


class QuestionOption(MultilingualLabelsMixin, RandomIDModel):
    class Meta:
        ordering = ('index',)

    def get_questionnaire(self):
        return self.question.questionnaire

    name = models.CharField(max_length=100)
    label = models.CharField(max_length=200)
    label_or_translations = JSONField()
    index = models.IntegerField(null=False)
    question = models.ForeignKey(Question, related_name='options')

    history = HistoricalRecords()
