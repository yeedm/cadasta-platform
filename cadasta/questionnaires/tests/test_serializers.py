import pytest
import os
from django.test import TestCase
from django.conf import settings

from buckets.test.storage import FakeS3Storage
from rest_framework.serializers import ValidationError

from organization.tests.factories import ProjectFactory
from questionnaires.exceptions import InvalidXLSForm
from core.tests.utils.files import make_dirs  # noqa

from . import factories
from .. import serializers
from ..models import Questionnaire, QuestionOption

path = os.path.dirname(settings.BASE_DIR)


@pytest.mark.usefixtures('make_dirs')
class QuestionnaireSerializerTest(TestCase):
    def _get_form(self, form_name):

        storage = FakeS3Storage()
        file = open(
            path + '/questionnaires/tests/files/{}.xlsx'.format(form_name),
            'rb'
        ).read()
        form = storage.save('xls-forms/{}.xlsx'.format(form_name), file)
        return form

    def test_deserialize(self):
        form = self._get_form('xls-form')

        project = ProjectFactory.create()

        serializer = serializers.QuestionnaireSerializer(
            data={'xls_form': form},
            context={'project': project}
        )
        assert serializer.is_valid(raise_exception=True) is True
        serializer.save()

        assert Questionnaire.objects.count() == 1
        questionnaire = Questionnaire.objects.first()

        assert questionnaire.id_string == 'question_types'
        assert questionnaire.filename == 'xls-form'
        assert questionnaire.title == 'Question types'

        assert serializer.data['id'] == questionnaire.id
        assert serializer.data['filename'] == questionnaire.filename
        assert serializer.data['title'] == questionnaire.title
        assert serializer.data['id_string'] == questionnaire.id_string
        assert serializer.data['xls_form'] == questionnaire.xls_form.url
        assert serializer.data['version'] == questionnaire.version
        assert len(serializer.data['questions']) == 1

    def test_deserialize_invalid_form(self):
        form = self._get_form('xls-form-invalid')

        project = ProjectFactory.create()

        serializer = serializers.QuestionnaireSerializer(
            data={'xls_form': form},
            context={'project': project}
        )
        assert serializer.is_valid(raise_exception=True) is True
        with pytest.raises(InvalidXLSForm):
            serializer.save()
        assert Questionnaire.objects.count() == 0

    def test_deserialize_json(self):
        data = {
            'title': 'yx8sqx6488wbc4yysnkrbnfq',
            'id_string': 'yx8sqx6488wbc4yysnkrbnfq',
            'questions': [{
                'name': "start",
                'label': None,
                'type': "ST",
                'required': False,
                'constraint': None
            }, {
                'name': "end",
                'label': None,
                'type': "EN",
            }]
        }
        project = ProjectFactory.create()

        serializer = serializers.QuestionnaireSerializer(
            data=data,
            context={'project': project}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        assert Questionnaire.objects.count() == 1
        questionnaire = Questionnaire.objects.first()
        assert project.current_questionnaire == questionnaire.id
        assert questionnaire.questions.count() == 2

    def test_invalid_deserialize_json(self):
        data = {
            'id_string': 'yx8sqx6488wbc4yysnkrbnfq',
            'questions': [{
                'name': "start",
                'label': None,
                'type': "ST",
                'required': False,
                'constraint': None
            }, {
                'name': "end",
                'label': None,
                'type': "EN",
            }]
        }
        project = ProjectFactory.create()

        serializer = serializers.QuestionnaireSerializer(
            data=data,
            context={'project': project}
        )
        assert serializer.is_valid() is False
        assert serializer.errors == {'title': ['This field is required.']}

        with pytest.raises(ValidationError):
            assert serializer.is_valid(raise_exception=True)

    def test_serialize(self):
        questionnaire = factories.QuestionnaireFactory()
        serializer = serializers.QuestionnaireSerializer(questionnaire)

        assert serializer.data['id'] == questionnaire.id
        assert serializer.data['filename'] == questionnaire.filename
        assert serializer.data['title'] == questionnaire.title
        assert serializer.data['id_string'] == questionnaire.id_string
        assert serializer.data['xls_form'] == questionnaire.xls_form.url
        assert serializer.data['version'] == questionnaire.version
        assert 'project' not in serializer.data


class QuestionGroupSerializerTest(TestCase):
    def test_serialize(self):
        questionnaire = factories.QuestionnaireFactory()
        question_group = factories.QuestionGroupFactory.create(
            questionnaire=questionnaire)
        factories.QuestionFactory.create_batch(
            2,
            questionnaire=questionnaire,
            question_group=question_group
        )
        not_in = factories.QuestionFactory.create(
            questionnaire=questionnaire
        )
        question_group.refresh_from_db()

        serializer = serializers.QuestionGroupSerializer(question_group)
        assert serializer.data['id'] == question_group.id
        assert serializer.data['name'] == question_group.name
        assert serializer.data['label'] == question_group.label
        assert len(serializer.data['questions']) == 2
        assert not_in.id not in [q['id'] for q in serializer.data['questions']]
        assert 'questionnaire' not in serializer.data

    def test_create_group(self):
        questionnaire = factories.QuestionnaireFactory.create()
        data = {
            'label': 'A question',
            'name': 'question'
        }
        serializer = serializers.QuestionGroupSerializer(
            data=data,
            context={'questionnaire_id': questionnaire.id})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        assert questionnaire.question_groups.count() == 1
        question = questionnaire.question_groups.first()
        assert question.name == data['name']
        assert question.label == data['label']

    def test_bulk_create_group(self):
        questionnaire = factories.QuestionnaireFactory.create()
        data = [{
                    'label': 'A group',
                    'name': 'group',
                    'questions': [{
                        'name': "start",
                        'label': None,
                        'type': "ST",
                    }]
                }, {
                    'label': 'Another group',
                    'name': 'another_group',
                    'questions': [{
                        'name': "end",
                        'label': None,
                        'type': "EN",
                    }]
                }]
        serializer = serializers.QuestionGroupSerializer(
            data=data,
            many=True,
            context={'questionnaire_id': questionnaire.id})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        assert questionnaire.question_groups.count() == 2

        for group in questionnaire.question_groups.all():
            assert group.questions.count()
            if group.name == 'group':
                assert group.questions.first().name == 'start'
            elif group.name == 'another_group':
                assert group.questions.first().name == 'end'


class QuestionSerializerTest(TestCase):
    def test_serialize(self):
        question = factories.QuestionFactory.create(
            default='some default',
            hint='An informative hint',
            relevant='${party_id}="abc123"'
        )
        serializer = serializers.QuestionSerializer(question)

        assert serializer.data['id'] == question.id
        assert serializer.data['name'] == question.name
        assert serializer.data['label'] == question.label
        assert serializer.data['type'] == question.type
        assert serializer.data['required'] == question.required
        assert serializer.data['constraint'] == question.constraint
        assert serializer.data['default'] == question.default
        assert serializer.data['hint'] == question.hint
        assert serializer.data['relevant'] == question.relevant
        assert 'options' not in serializer.data
        assert 'questionnaire' not in serializer.data
        assert 'question_group' not in serializer.data

    def test_serialize_with_options(self):
        question = factories.QuestionFactory.create(type='S1')
        factories.QuestionOptionFactory.create_batch(2, question=question)
        serializer = serializers.QuestionSerializer(question)

        assert serializer.data['id'] == question.id
        assert serializer.data['name'] == question.name
        assert serializer.data['label'] == question.label
        assert serializer.data['type'] == question.type
        assert serializer.data['required'] == question.required
        assert serializer.data['constraint'] == question.constraint
        assert len(serializer.data['options']) == 2
        assert 'questionnaire' not in serializer.data
        assert 'question_group' not in serializer.data

    def test_create_question(self):
        questionnaire = factories.QuestionnaireFactory.create()
        data = {
            'label': 'A question',
            'name': 'question',
            'type': 'TX'
        }
        serializer = serializers.QuestionSerializer(
            data=data,
            context={'questionnaire_id': questionnaire.id})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        assert questionnaire.questions.count() == 1
        question = questionnaire.questions.first()
        assert question.label == data['label']
        assert question.type == data['type']
        assert question.name == data['name']

    def test_with_options(self):
        questionnaire = factories.QuestionnaireFactory.create()
        data = {
            'label': 'A question',
            'name': 'question',
            'type': 'S1',
            'options': [{
                'label': 'An option',
                'name': 'option',
                'index': 0
            }]
        }
        serializer = serializers.QuestionSerializer(
            data=data,
            context={'questionnaire_id': questionnaire.id})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        assert questionnaire.questions.count() == 1
        question = questionnaire.questions.first()
        assert question.label == data['label']
        assert question.type == data['type']
        assert question.name == data['name']
        assert QuestionOption.objects.count() == 1
        assert question.options.count() == 1

    def test_bulk_create(self):
        questionnaire = factories.QuestionnaireFactory.create()
        data = [{
            'label': 'A question',
            'name': 'question',
            'type': 'TX'
        }, {
            'label': 'Another question',
            'name': 'another_question',
            'type': 'S1',
            'options': [{
                'label': 'An option',
                'name': 'option',
                'index': 0
            }]
        }]
        serializer = serializers.QuestionSerializer(
            data=data,
            many=True,
            context={'questionnaire_id': questionnaire.id})
        serializer.is_valid(raise_exception=True)
        serializer.save()

        questions = questionnaire.questions.all()
        assert questions.count() == 2

        for q in questions:
            if q.name == 'question':
                assert q.label == 'A question'
                assert q.type == 'TX'
                assert q.options.count() == 0
            if q.name == 'another_question':
                assert q.label == 'Another question'
                assert q.type == 'S1'
                assert q.options.count() == 1


class QuestionOptionSerializerTest(TestCase):
    def test_serialize(self):
        question_option = factories.QuestionOptionFactory.create()
        serializer = serializers.QuestionOptionSerializer(question_option)

        assert serializer.data['id'] == question_option.id
        assert serializer.data['name'] == question_option.name
        assert serializer.data['label'] == question_option.label
        assert 'question' not in serializer.data

    def test_create_option(self):
        question = factories.QuestionFactory.create()
        data = {
            'name': 'option',
            'label': 'An option',
            'index': 0
        }
        serializer = serializers.QuestionOptionSerializer(
            data=data,
            context={'question_id': question.id})
        serializer.is_valid()
        serializer.save()

        assert QuestionOption.objects.count() == 1
        option = QuestionOption.objects.first()
        assert option.name == data['name']
        assert option.label == data['label']
        assert option.question_id == question.id

    def test_bulk_create(self):
        question = factories.QuestionFactory.create()
        data = [{
            'name': 'option',
            'label': 'An option',
            'index': 0
        }, {
            'name': 'option_2',
            'label': 'Another',
            'index': 1
        }]
        serializer = serializers.QuestionOptionSerializer(
            data=data,
            many=True,
            context={'question_id': question.id})
        serializer.is_valid()
        serializer.save()
        assert question.options.count() == 2
