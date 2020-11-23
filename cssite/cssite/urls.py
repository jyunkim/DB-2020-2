"""cssite URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/3.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from collect.views import *

urlpatterns = [
    path('admin/', admin.site.urls),
    path('collect/', include('collect.urls')),

    path('upload/', uploadFile, name='upload file'),
    path('list/', fileList, name='list files'),

    path('task/', listTasks, name='list tasks'),
    path('task/<int:task_id>/', showTask, name='show task'),
    path('task/create/', createTask, name='create task'),

    path('task/<int:task_id>/attribute/',
         listAttributes, name='list attributes'),
    path('task/<int:task_id>/attribute/create/',
         createAttribute, name='create attribute'),

    path('task/<int:task_id>/derived_schema/',
         listDerivedSchemas, name='list derived schemas'),
    path('task/<int:task_id>/derived_schema/<int:schema_id>/',
         showDerivedSchema, name='show derived schema'),
    path('task/<int:task_id>/derived_schema/create/',
         createDerivedSchema, name='create derived schema'),
    path('task/<int:task_id>/derived_schema/<int:schema_id>/pair/',
         listMappingPairs, name='list mapping pairs'),
    path('task/<int:task_id>/derived_schema/<int:schema_id>/pair/create',
         createMappingPair, name='create mapping pair'),

]