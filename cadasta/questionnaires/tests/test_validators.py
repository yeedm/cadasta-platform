from django.test import TestCase
from .. import validators


class ValidateTypeTest(TestCase):
    def test_validate_string(self):
        assert validators.validate_type('string', 'akshdk') is True
        assert validators.validate_type('string', 1) is False
        assert validators.validate_type('string', True) is False
        assert validators.validate_type('string', []) is False

    def test_validate_number(self):
        assert validators.validate_type('number', 'akshdk') is False
        assert validators.validate_type('number', 1) is True
        assert validators.validate_type('number', True) is False
        assert validators.validate_type('number', []) is False

    def test_validate_boolean(self):
        assert validators.validate_type('boolean', 'akshdk') is False
        assert validators.validate_type('boolean', 1) is False
        assert validators.validate_type('boolean', True) is True
        assert validators.validate_type('boolean', []) is False

    def test_validate_array(self):
        assert validators.validate_type('array', 'akshdk') is False
        assert validators.validate_type('array', 1) is False
        assert validators.validate_type('array', True) is False
        assert validators.validate_type('array', []) is True


class ValidateSchemaTest(TestCase):
    SCHEMA = {
        'title': {
            'type': 'string',
            'required': True
        },
        'id_string': {
            'type': 'string',
            'required': True
        },
        'some_list': {
            'type': 'string',
            'enum': ['A', 'B', 'C']
        }
    }

    def test_valid_schema(self):
        data = {
            'title': 'Title',
            'id_string': 'askljdaskljdl',
            'some_list': 'A'
        }
        assert validators.validate_schema(self.SCHEMA, data) == {}

    def test_invalid_schema(self):
        data = {
            'id_string': 123,
            'some_list': 'D'
        }
        errors = validators.validate_schema(self.SCHEMA, data)
        assert 'This field is required.' in errors['title']
        assert 'Value must be of type string.' in errors['id_string']
        assert 'D is not an accepted value.' in errors['some_list']


class QuestionnaireTestCase(TestCase):
    def test_valid_questionnaire(self):
        data = {
            'title': 'yx8sqx6488wbc4yysnkrbnfq',
            'id_string': 'yx8sqx6488wbc4yysnkrbnfq',
            'questions': [{
                'name': "start",
                'label': None,
                'type': "ST",
                'required': False,
                'constraint': None
            }]
        }
        errors = validators.validate_questionnaire(data)
        assert errors is None

    def test_invalid_questionnaire(self):
        data = {
            'questions': [{
                'label': None,
                'type': "ST",
                'required': False,
                'constraint': None
            }],
            'question_groups': [{
                'label': 'A group'
            }]
        }
        errors = validators.validate_questionnaire(data)
        assert 'This field is required.' in errors['title']
        assert 'This field is required.' in errors['id_string']
        assert 'This field is required.' in errors['questions'][0]['name']
        assert ('This field is required.' in
                errors['question_groups'][0]['name'])


class QuestionGroupTestCase(TestCase):
    def test_valid_questiongroup(self):
        data = [{
            'name': "location_attributes",
            'label': "Location Attributes",
            'questions': [{
                'name': "start",
                'label': 'Start',
                'type': "ST",
            }]
        }]
        errors = validators.validate_question_groups(data)
        assert errors == [{}]

    def test_invalid_questiongroup(self):
        data = [{
            'label': "location attributes",
            'questions': [{
                'label': 'Start',
                'type': "ST",
            }]
        }]
        errors = validators.validate_question_groups(data)
        assert errors == [{'name': ['This field is required.'],
                           'questions': [
                                {'name': ['This field is required.']}
                            ]}
                          ]


class QuestionTestCase(TestCase):
    def test_valid_question(self):
        data = [{
            'name': "start",
            'label': None,
            'type': "ST",
            'required': False,
            'constraint': None
        }]
        errors = validators.validate_questions(data)
        assert errors == [{}]

    def test_invalid_question(self):
        data = [{
            'name': "start",
            'label': None,
            'type': "ST",
            'required': False,
            'constraint': None
        }, {
            'label': None,
            'type': "S1",
            'required': False,
            'constraint': None,
            'options': [{'name': 'Name'}]
        }]
        errors = validators.validate_questions(data)
        assert errors == [{},
                          {'name': ['This field is required.'],
                           'options': [{'label': ['This field is required.']}]}
                          ]


class QuestionOptionTestCase(TestCase):
    def test_valid_option(self):
        data = [{
            'name': "start",
            'label': "Start",
        }]
        errors = validators.validate_question_options(data)
        assert errors == [{}]

    def test_invalid_option(self):
        data = [{
            'name': "start",
            'label': "Start",
        }, {
            'name': 'end'
        }]
        errors = validators.validate_question_options(data)
        assert errors == [{}, {'label': ['This field is required.']}]
