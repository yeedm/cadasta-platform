from buckets.serializers import S3Field
from rest_framework import serializers

from .validators import validate_questionnaire
from . import models


class QuestionOptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.QuestionOption
        fields = ('id', 'name', 'label', 'index', )
        read_only_fields = ('id',)

    def create(self, validated_data):
        validated_data['question_id'] = self.context.get('question_id')
        return super().create(validated_data)


class QuestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Question
        fields = ('id', 'name', 'label', 'type', 'required', 'constraint',
                  'default', 'hint', 'relevant', )
        read_only_fields = ('id', )

    def to_representation(self, instance):
        rep = super().to_representation(instance)

        if (isinstance(instance, models.Question) and instance.has_options):
            serializer = QuestionOptionSerializer(instance.options, many=True)
            rep['options'] = serializer.data

        return rep

    def find_options(self, name):
        if isinstance(self.initial_data, list):
            for question in self.initial_data:
                if question['name'] == name:
                    return question.get('options', [])

        return self.initial_data.get('options', [])

    def create(self, validated_data):
        question = models.Question.objects.create(
            questionnaire_id=self.context.get('questionnaire_id'),
            question_group_id=self.context.get('question_group_id'),
            **validated_data)

        option_serializer = QuestionOptionSerializer(
                data=self.find_options(question.name),
                many=True,
                context={'question_id': question.id})

        option_serializer.is_valid(raise_exception=True)
        option_serializer.save()

        return question


class QuestionGroupSerializer(serializers.ModelSerializer):
    questions = QuestionSerializer(many=True, read_only=True)

    class Meta:
        model = models.QuestionGroup
        fields = ('id', 'name', 'label', 'questions',)
        read_only_fields = ('id', 'questions',)

    def find_questions(self, name):
        if isinstance(self.initial_data, list):
            for group in self.initial_data:
                if group['name'] == name:
                    return group.get('questions', [])

        return self.initial_data.get('questions', [])

    def create(self, validated_data):
        group = models.QuestionGroup.objects.create(
            questionnaire_id=self.context.get('questionnaire_id'),
            **validated_data)

        question_serializer = QuestionSerializer(
                data=self.find_questions(group.name),
                many=True,
                context={
                    'question_group_id': group.id,
                    'questionnaire_id': self.context.get('questionnaire_id')
                }
            )

        question_serializer.is_valid(raise_exception=True)
        question_serializer.save()

        return group


class QuestionnaireSerializer(serializers.ModelSerializer):
    xls_form = S3Field(required=False)
    id_string = serializers.CharField(
        max_length=50, required=False, default=''
    )
    version = serializers.IntegerField(required=False, default=1)
    questions = serializers.SerializerMethodField()
    question_groups = QuestionGroupSerializer(many=True, read_only=True)

    class Meta:
        model = models.Questionnaire
        fields = (
            'id', 'filename', 'title', 'id_string', 'xls_form',
            'version', 'questions', 'question_groups', 'md5_hash'
        )
        read_only_fields = (
            'id', 'filename', 'title', 'id_string', 'version',
            'questions', 'question_groups'
        )

    def validate_json(self, json, raise_exception=False):
        errors = validate_questionnaire(json)
        self._validated_data = json
        self._errors = {}

        if errors:
            self._validated_data = {}
            self._errors = errors

            if raise_exception:
                raise serializers.ValidationError(self.errors)

        return not bool(self._errors)

    def is_valid(self, **kwargs):
        if 'xls_form' in self.initial_data:
            return super().is_valid(**kwargs)
        else:
            return self.validate_json(self.initial_data, **kwargs)

    def create(self, validated_data):
        project = self.context['project']
        if 'xls_form' in validated_data:
            form = validated_data['xls_form']
            instance = models.Questionnaire.objects.create_from_form(
                xls_form=form,
                project=project
            )
            return instance
        else:
            questions = validated_data.pop('questions', [])
            instance = models.Questionnaire.objects.create(
                project=project,
                **validated_data)

            question_serializer = QuestionSerializer(
                data=questions,
                many=True,
                context={'questionnaire_id': instance.id})
            question_serializer.is_valid(raise_exception=True)
            question_serializer.save()

            project.current_questionnaire = instance.id
            project.save()

            return instance

    def get_questions(self, instance):
        questions = instance.questions.filter(question_group__isnull=True)
        serializer = QuestionSerializer(questions, many=True)
        return serializer.data
