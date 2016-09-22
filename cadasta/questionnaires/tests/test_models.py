from django.test import TestCase
from .factories import QuestionFactory, QuestionnaireFactory


class QuestionnaireTest(TestCase):
    def test_save(self):
        questionnaire = QuestionnaireFactory.build()
        questionnaire.version = None
        questionnaire.md5_hash = None

        questionnaire.save()
        assert questionnaire.version is not None
        assert questionnaire.md5_hash is not None

        questionnaire = QuestionnaireFactory.build(
            version=129839021903,
            md5_hash='sakohjd89su90us9a0jd90sau90d'
        )

        questionnaire.save()
        assert questionnaire.version == 129839021903
        assert questionnaire.md5_hash == 'sakohjd89su90us9a0jd90sau90d'


class QuestionTest(TestCase):
    def test_has_options(self):
        question = QuestionFactory.create(type='S1')
        assert question.has_options is True

        question = QuestionFactory.create(type='SM')
        assert question.has_options is True

        question = QuestionFactory.create(type='IN')
        assert question.has_options is False
