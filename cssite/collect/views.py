from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render, get_object_or_404, get_list_or_404, redirect
from django.urls import reverse
from django.views import generic, View
from django.contrib import auth, messages
from django.contrib.auth.models import User
from .models import Account, Task, Participation, ParsedFile, SchemaAttribute, MappingInfo, MappingPair, OriginFile
from .forms import LoginForm, GradeForm, SchemaChoiceForm, UploadForm, CreateTask, CreateSchemaAttribute, CreateMappingInfo, CreateMappingPair
from datetime import date, datetime
import os
import pandas as pd
from django.conf import settings


# 홈
def index(request):
    return render(request, 'collect/index.html')


def fileList(request):
    """
    docstring
    """
    return render(request, 'pages/list.html', {
        'files': str(list(OriginFile.objects.values())),
        'files_parsed': str(list(ParsedFile.objects.values())),
    })

# 회원가입


def signup(request):
    context = {}
    if request.method == "POST":
        if request.POST["password1"] == request.POST["password2"]:
            user = User.objects.create_user(
                username=request.POST["username"],
                password=request.POST["password1"])
            account = Account(
                user=user,
                name=request.POST["name"],
                contact=request.POST["contact"],
                birth=request.POST["birth"],
                gender=request.POST["gender"],
                address=request.POST["address"],
                role=request.POST["role"])
            account.save()
            auth.login(request, user)
            if account.role == '제출자':
                return redirect(reverse('collect:submitter'))
            elif account.role == '평가자':
                return redirect(reverse('collect:grader'))
        else:
            context.update({'error': "비밀번호가 일치하지 않습니다."})
    return render(request, 'collect/signup.html', context)

# 로그인


def login(request):
    if request.method == "POST":
        username = request.POST['username']
        password = request.POST['password']
        user = auth.authenticate(request, username=username, password=password)
        if user is not None:
            auth.login(request, user)
            if user.account.role == '제출자':
                return redirect(reverse('collect:submitter'))
            elif user.account.role == '평가자':
                return redirect(reverse('collect:grader'))
        messages.error(request, '로그인 실패. 다시 시도 해보세요.')
        return render(request, 'collect/login.html')
    else:
        return render(request, 'collect/login.html')


# 로그아웃
def logout(request):
    auth.logout(request)
    return redirect(reverse('collect:index'))


# 정보 조회
def userinfo(request, pk):
    user = request.user
    account = user.account
    context = {
        'user': user,
        'account': account
    }
    return render(request, 'collect/userinfo.html', context)


# 회원 정보 수정
def update(request, pk):
    if request.method == "POST":
        user = request.user
        if request.POST["password1"] == request.POST["password2"]:
            user.set_password(request.POST["password1"])
            user.save()
            account = user.account
            account.name = request.POST["name"]
            account.contact = request.POST["contact"]
            account.birth = request.POST["birth"]
            account.gender = request.POST["gender"]
            account.address = request.POST["address"]
            account.save()
            auth.login(request, user)
            if account.role == '제출자':
                return redirect(reverse('collect:tasks'))
            elif account.role == '평가자':
                return redirect(reverse('collect:allocated-parsedfiles'))
    return render(request, 'collect/update.html')

# 회원 탈퇴


def delete(request, pk):
    user = User.objects.get(pk=pk)
    user.delete()
    return redirect(reverse('collect:index'))


# 태스크 목록
class TaskList(View):
    def get(self, request):
        account = request.user.account
        task_list = Task.objects.all()
        participations = Participation.objects.filter(account=account)
        participate_tasks = [
            participation.task for participation in participations]
        context = {
            'task_list': task_list,
            'participate_tasks': participate_tasks
        }
        return render(request, 'collect/task.html', context)


# 태스크 상세 정보
class TaskDetail(generic.DetailView):
    model = Task
    context_object_name = 'task'
    template_name = 'collect/task_detail.html'


# 태스크 참여
def create_participation(request, pk):
    user = request.user
    task = get_object_or_404(Task, pk=pk)
    participation = Participation(account=user.account, task=task)
    participation.save()
    return redirect(reverse('collect:participations'))


# 참여 중인 태스크 목록
class ParticipationList(View):
    def get(self, request):
        user = request.user
        participations = user.account.participations.all()
        return render(request, 'collect/participation.html', {'participations': participations})


# 태스크 참여 취소, 관리자 승인
def delete_participation(request, pk):
    if request.user.is_superuser:
        participation = get_object_or_404(Participation, pk=pk)
        participation.admission = True
        participation.save()
        return redirect(reverse('collect:users'))
    else:
        participation = get_object_or_404(Participation, pk=pk)
        participation.delete()
        return redirect(reverse('collect:participations'))


# 제출한 파일 목록
class ParsedfileList(View):
    def get(self, request, pk):
        user = request.user
        task = get_object_or_404(Task, pk=pk)
        parsedfile_list = user.account.parsed_submits.filter(task=task)
        total_tuple = sum(
            parsedfile.total_tuple for parsedfile in parsedfile_list)
        context = {
            'task': task,
            'parsedfile_list': parsedfile_list,
            'total_tuple': total_tuple
        }
        return render(request, 'collect/submitted_parsedfile.html', context)


# 평가된 파일 목록
class GradedfileList(View):
    def get(self, request):
        user = request.user
        parsedfiles = user.account.parsed_grades.filter(
            grading_score__isnull=False)
        return render(request, 'collect/graded_parsedfile.html', {'parsedfiles': parsedfiles})


# 할당된 파일 목록
class AllocatedfileList(View):
    def get(self, request):
        user = request.user
        parsedfiles = user.account.parsed_grades.filter(
            grading_score__isnull=True)
        now = date.today()
        context = {
            'parsedfiles': parsedfiles,
            'now': now
        }
        return render(request, 'collect/allocated_parsedfile.html', context)


# 파일 평가
def grade_parsedfile(request, pk):
    if request.method == "POST":
        form = GradeForm(request.POST)
        parsedfile = get_object_or_404(ParsedFile, pk=pk)
        if form.is_valid():
            parsedfile.grading_score = form.cleaned_data['grading_score']
            parsedfile.pass_state = form.cleaned_data['pass_state']
            parsedfile.save()
            return redirect(reverse('collect:graded-parsedfiles'))
        context = {
            'form': form,
            'parsedfile': parsedfile
        }
        context.update({'error': '0 ~ 10 사이의 숫자를 입력해주세요.'})
        return render(request, 'collect/grade.html', context)
    else:
        form = GradeForm()
        parsedfile = get_object_or_404(ParsedFile, pk=pk)
        context = {
            'form': form,
            'parsedfile': parsedfile
        }
        return render(request, 'collect/grade.html', context)

# 유저 검색


class UserList(View):
    def get(self, request):
        tasks = Task.objects.all()
        accounts = Account.objects.all()
        username = request.GET.get('username')
        gender = request.GET.get('gender')
        role = request.GET.get('role')
        birth1 = request.GET.get('birth1')
        birth2 = request.GET.get('birth2')
        taskname = request.GET.get('taskname')
        if username:
            accounts = accounts.filter(user__username__contains=username)
        if gender:
            accounts = accounts.filter(gender__exact=gender)
        if role:
            accounts = accounts.filter(role__exact=role)
        if birth1 and birth2:
            accounts = accounts.filter(birth__range=(birth1, birth2))
        if taskname:
            task = Task.objects.get(name=taskname)
            accounts = accounts.filter(
                participations__in=task.participations.all())
        context = {
            'accounts': accounts,
            'tasks': tasks
        }
        return render(request, 'collect/userlist.html', context)


# 유저 상세 정보
class UserDetail(View):
    def get(self, request, pk):
        user = User.objects.get(pk=pk)
        if user.account.role == '제출자':
            participations = user.account.participations.all()
            return render(request, 'collect/participation.html', {'participations': participations})
        elif user.account.role == '평가자':
            user = User.objects.get(pk=pk)
            parsedfiles = user.account.parsed_grades.filter(
                grading_score__isnull=False)
            return render(request, 'collect/graded_parsedfile.html', {'parsedfiles': parsedfiles})


def submitter(request):
    return render(request, 'collect/submitter.html')


def grader(request):
    return render(request, 'collect/grader.html')


def uploadFile(request):
    """
    docstring
    """
    form = None
    # schema_choice_form = None
    saved_original_file = None
    if request.method == 'POST':
        form = UploadForm(request.POST, request.FILES)
        # schema_choice_form = SchemaChoiceForm(request.POST, request.FILES)
        if form.is_valid():
            # form = form.save(commit=False) # 중복 DB save를 방지
            saved_original_file = form.save()
        # elif schema_choice_form.is_valid():

    else:
        form = UploadForm()
        # schema_choice_form = SchemaChoiceForm()

    if saved_original_file:
        # TODO: 이 부분 구현해야 합니다!
        # 각 릴레이션의 튜풀을 받아야 합니다.
        # 이런 식으로요:
        # task = Task.objects.filter(***)[0]
        # 아마 key 등을 이 함수의 파라미터를 통해 받아오는 방법 등을 택할 것 같네요.
        task_name = "test_task"
        submitter_pk = "test_id"
        grader_pk = "test_id"

        task = Task.objects.filter(name=task_name)[0]
        submitter = Account.objects.filter(id=submitter_pk)[0]
        grader = Account.objects.filter(id=grader_pk)[0]

        derived_schema = saved_original_file.derived_schema

        # print(saved_original_file.get_absolute_path(), "###")
        # load csv file from the server
        df = pd.read_csv(saved_original_file.get_absolute_path())

        # get DB tuples
        mapping_info = MappingInfo.objects.filter(
            task=task,
            derived_schema_name=derived_schema
        )[0]

        # get parsing information into a dictionary
        # { 파싱전: 파싱후 }
        mapping_from_to = {
            i.parsing_column_name: i.schema_attribute.attr
            for i in MappingPair.objects.filter(
                mapping_info=mapping_info
            )
        }

        # parse
        for key in df.columns:
            if key in mapping_from_to.keys():
                df.rename(columns={key: mapping_from_to[key]}, inplace=True)
            else:
                df.drop([key], axis='columns', inplace=True)

        # save the parsed file
        parsed_file_path = os.path.join(settings.MEDIA_ROOT, str(
            saved_original_file).replace('data_original/', 'data_parsed/'))
        df.to_csv(parsed_file_path, index=False)

        # increment submit count of Participation tuple by 1
        participation = Participation.objects.filter(
            account=submitter, task=task)[0]
        participation.submit_count += 1
        participation.save()

        # make statistic
        # print(df.isnull().sum()/(len(df)*len(df.columns)), "###")
        duplicated_tuple = len(df)-len(df.drop_duplicates())
        null_ratio = df.isnull().sum().sum()/(len(df)*len(df.columns)
                                              ) if (len(df)*len(df.columns)) > 0 else 1
        parsed_file = ParsedFile(
            task=task,
            submitter=submitter,
            grader=grader,
            submit_count=participation.submit_count,
            start_date=datetime.now(),  # TODO: should be implemented that user can select the date
            end_date=datetime.now(),    # TODO: should be implemented that user can select the date
            total_tuple=len(df),
            duplicated_tuple=duplicated_tuple,
            null_ratio=null_ratio,
            # grading_score=,   # TODO: should be immplemented
            pass_state=False,
            grading_end_date=datetime.now(),    # TODO: should be implemented
        )

        # save the parsed file
        # print(df)
        parsed_file.file_original = str(saved_original_file)
        parsed_file.file_parsed = str(saved_original_file).replace(
            'data_original/', 'data_parsed/')
        parsed_file.save()

        # TODO: data too long error
        # select @@global.sql_mode;  # SQL 설정 보기
        # remove: "STRICT_TRANS_TABLES"
        # set @@global.sql_mode="ONLY_FULL_GROUP_BY,NO_ZERO_IN_DATE,NO_ZERO_DATE,ERROR_FOR_DIVISION_BY_ZERO,NO_ENGINE_SUBSTITUTION";

        # TODO: Return 부분 수정해야함
        return redirect('list files')

    return render(request, 'pages/upload.html', {
        'file_upload_form': form
    })


def generateListString(iterable):
    """
    1. each element of iterable contains .__str__()
    2. use |linebreaks tag on template html file to display
    """
    text = ""
    for i in iterable:
        text += i.__str__()
        text += '\n'
    return text


"""
view functions for task
"""


def listTasks(request):
    """
    docstring
    """
    tasks = generateListString(Task.objects.values())
    return render(request, 'pages/task_list.html', {
        'list_of_tasks': tasks,
    })


def showTask(request, task_id):
    """
    docstring
    """
    task = Task.objects.filter(id=task_id)[0]
    attributes = generateListString(SchemaAttribute.objects.filter(task=task))
    derived_schemas = generateListString(MappingInfo.objects.filter(task=task))
    return render(request, 'pages/task_select.html', {
        'task_name': task.name,
        'task_info': str(list(Task.objects.filter(id=task_id).values())),
        'task_attributes': attributes,
        'task_derived_schemas': derived_schemas,
    })


def createTask(request):
    """
    docstring
    """

    form = None
    task = None
    if request.method == 'POST':
        form = CreateTask(request.POST, request.FILES)
        if form.is_valid():
            # form = form.save(commit=False) # 중복 DB save를 방지
            task = form.save()
            # task.activation_state = True
            task.save()

            # return render(request, 'pages/done_task.html', {})
            return redirect('list tasks')
    else:
        form = CreateTask()

    # name = "test_task"
    # minimal_upload_frequency = 0
    # description = "test_desc"
    # original_data_description = "what is this?"

    # task = Task(
    #     name=name,
    #     minimal_upload_frequency=minimal_upload_frequency,
    #     activation_state=True,
    #     description=description,
    #     original_data_description=original_data_description
    # )

    return render(request, 'pages/task_create.html', {
        'create_task_form': form
    })


"""
view functions for attribute
"""


def listAttributes(request, task_id):
    """
    docstring
    """
    task = Task.objects.filter(id=task_id)[0]
    attributes = generateListString(SchemaAttribute.objects.filter(task=task))
    return render(request, 'pages/attribute_list.html', {
        'task_name': task.name,
        'list_of_attributes': attributes,
    })


def createAttribute(request, task_id):
    """
    docstring
    """
    form = None
    task = Task.objects.filter(id=task_id)[0]
    attribute = None

    if task.activation_state:
        return HttpResponse("<h2>태스크가 활성화되어 있습니다!</h3>")

    attributes = generateListString(SchemaAttribute.objects.filter(task=task))

    if request.method == 'POST':
        form = CreateSchemaAttribute(request.POST, request.FILES)
        if form.is_valid():
            # form = form.save(commit=False) # 중복 DB save를 방지
            attribute = form.save(task)
            # attribute.task = task
            attribute.save()

            return redirect('create attribute', task_id=task_id)

    else:
        form = CreateSchemaAttribute()

    return render(request, 'pages/attribute_create.html', {
        'create_attribute_form': form,
        'list_of_attributes': attributes,
    })


"""
view functions for derived schema
"""


def listDerivedSchemas(request, task_id):
    """
    docstring
    """
    task = Task.objects.filter(id=task_id)[0]
    derived_schemas = generateListString(MappingInfo.objects.filter(task=task))
    return render(request, 'pages/derived_schema_list.html', {
        'task_name': task.name,
        'list_of_derived_schemas': derived_schemas,
    })


def showDerivedSchema(request, task_id, schema_id):
    """
    docstring
    """
    task = Task.objects.filter(id=task_id)[0]
    schema = MappingInfo.objects.filter(id=schema_id, task=task)[0]

    schema_info = MappingInfo.objects.filter(id=schema_id).values()[0]
    mapping_pairs = generateListString(
        MappingPair.objects.filter(mapping_info=schema))
    return render(request, 'pages/derived_schema_select.html', {
        'task_name': task.name,
        'schema_name': schema.derived_schema_name,
        'schema_info': schema_info,
        'mapping_pairs': mapping_pairs,
    })


def createDerivedSchema(request, task_id):
    """
    docstring
    """
    form = None
    task = Task.objects.filter(id=task_id)[0]
    schema = None
    if request.method == 'POST':
        form = CreateMappingInfo(request.POST, request.FILES)
        if form.is_valid():
            # form = form.save(commit=False) # 중복 DB save를 방지
            schema = form.save(task)
            # schema.task = task
            schema.save()

            return redirect('list derived schemas', task_id=task_id)

    else:
        form = CreateMappingInfo()

    return render(request, 'pages/derived_schema_create.html', {
        'create_derived_schema_form': form
    })


"""
view functions for mapping pairs
"""


def listMappingPairs(request, task_id, schema_id):
    """
    docstring
    """
    task = Task.objects.filter(id=task_id)[0]
    derived_schema = MappingInfo.objects.filter(id=schema_id, task=task)[0]

    mapping_pairs = generateListString(
        MappingPair.objects.filter(mapping_info=derived_schema))
    return render(request, 'pages/mapping_pair_list.html', {
        'task_name': task.name,
        'schema_name': derived_schema.derived_schema_name,
        'list_of_mapping_pairs': mapping_pairs,
    })


def createMappingPair(request, task_id, schema_id):
    """
    docstring
    """
    form = None
    task = Task.objects.filter(id=task_id)[0]
    derived_schema = MappingInfo.objects.filter(id=schema_id, task=task)[0]

    mapping_pairs = generateListString(
        MappingPair.objects.filter(mapping_info=derived_schema))

    mapping_pair = None
    if request.method == 'POST':
        form = CreateMappingPair(request.POST, request.FILES)
        if form.is_valid():
            # form = form.save(commit=False) # 중복 DB save를 방지
            mapping_pair = form.save(derived_schema)
            # schema.task = task
            mapping_pair.save()

            return redirect('create mapping pair', task_id=task_id, schema_id=schema_id)

    else:
        form = CreateMappingPair()

    return render(request, 'pages/mapping_pair_create.html', {
        'create_mapping_pair_form': form,
        'list_of_mapping_pairs': mapping_pairs,
    })