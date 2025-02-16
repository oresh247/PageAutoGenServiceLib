# coding:utf-8
import warnings
import configparser
import requests
import json
import re
import pandas as pd
import numpy as np
import html

warnings.filterwarnings("ignore")

config = configparser.ConfigParser()
configJira = configparser.ConfigParser()
config.read("config.ini", encoding='utf-8')
configJira.read("configFields.ini", encoding='utf-8')

# СФЕРА параметры
devUser = config["SFERAUSER"]["devUser"]
devPassword = config["SFERAUSER"]["devPassword"]
sferaUrlLogin = config["SFERA"]["sferaUrlLogin"]
sferaUrlGetFile = config["SFERA"]["sferaUrlGetFile"]
sferaUrlKnowledge = config["SFERA"]["sferaUrlKnowledge"]
sferaUrlKnowledge2 = config["SFERA"]["sferaUrlKnowledge2"]
sferaUrlOrchestration = config["SFERA"]["sferaUrlOrchestration"]

SERVICE_LST = json.loads(config["ORCHESTRATION"]["SERVICE_LST"])
LIB_LST = json.loads(config["ORCHESTRATION"]["LIB_LST"])
FILE_NAME = config["ORCHESTRATION"]["FILE_NAME"]

session = requests.Session()
session.post(sferaUrlLogin, json={"username": devUser, "password": devPassword}, verify=False)

def get_file(project, build, file_name):
    url = sferaUrlGetFile + project + "/builds/" + build + "/downloadArtefact/?fullName=/SCA/" + file_name
    response = session.get(url, verify=False)
    if response.ok != True:
        print("Error get file " + file_name)
        return None
    return response.text


def get_version(dependency, lib_name):
    pattern = re.compile(rf".*([:]){lib_name}[:](.*)")
    for line in dependency.splitlines():
        match = pattern.search(line)
        if match:
            return match.group(2).strip()
    return "None"


def get_builds(project):
    url = sferaUrlGetFile + project + "/builds/?page=0&size=10&sort=startTime,desc"
    response = session.get(url, verify=False)
    if response.ok != True:
        raise Exception("Error get sprint data " + response)
    return json.loads(response.text)


def get_release_build_id(builds):
    # Перебираем содержимое сборок
    if builds['content'] == None: return None, None
    for build in builds.get("content", []):
        display_name = build.get("displayName", "")
        if display_name.endswith("-release"):
            return build.get("id"), display_name
    return None, None


def get_lib_version_list(gradle_dependency_tree):
    version_lst = []
    for lib_name in LIB_LST:
        version = get_version(gradle_dependency_tree, lib_name)
        version_lst.append(version)
    return version_lst


def create_empty_dataframe():
    # Создаем пустой DataFrame с указанными столбцами
    df = pd.DataFrame(columns=["service", "build"] + LIB_LST)
    # Устанавливаем "service" как индекс
    df.index.name = 'service'
    return df


def add_service_to_dataframe(df, service, release_build_name, lib_version_list):
    # Создаем словарь с данными для новой строки
    new_row = {'service': service}  # Добавляем build в строку
    new_row['build'] = release_build_name

    # Заполняем версии библиотек из списка
    for i, lib in enumerate(df.columns):
        if lib != 'build' and lib != 'service':  # Пропускаем столбец 'build', потому что он уже добавлен
            new_row[lib] = lib_version_list[i-2]

    # Добавляем новую строку в DataFrame, указав service в качестве индекса
    df.loc[service] = new_row
    return df


def get_service_list():
    url = sferaUrlOrchestration
    response = session.get(url, verify=False)
    if response.ok != True:
        print("Error get service list")
        return None
    return json.loads(response.text)


def get_all_service():
    service_names = []
    url = sferaUrlOrchestration
    response = session.get(url, verify=False)
    if response.ok != True: return None
    for item in json.loads(response.text)["data"]:
        if "name" in item:
            service_names.append(item["name"])
    return service_names


def get_service_id(service, skmb_service_list):
    for item in skmb_service_list["data"]:
        if "name" in item and item["name"] == service:
            return item["id"]

    return None  # Сервис не найден


def get_service_lib_versions():
    df = create_empty_dataframe()
    skmb_service_list = get_service_list()
    for service in SERVICE_LST:
        project = get_service_id(service, skmb_service_list)
        if project == None: continue
        # Вызываем функцию get_builds, передавая значение project
        builds = get_builds(project)
        release_build_id, release_build_name = get_release_build_id(builds)
        if release_build_id == None: continue
        gradle_dependency_tree = get_file(project, str(release_build_id),FILE_NAME)
        if gradle_dependency_tree == None: continue
        lib_version_list = get_lib_version_list(gradle_dependency_tree)
        df = add_service_to_dataframe(df, service, release_build_name, lib_version_list)
    return df


def generate_release_html(df):
    # Генерируем HTML-код
    html_code = df.to_html(index=False)
    print(html_code)

    # Декодируем HTML-спецсимволы
    decoded_html = html.unescape(html_code)
    decoded_html = str.replace(decoded_html, '"', '')

    # decoded_html = str.replace(decoded_html, '\\n', '')
    # decoded_html = str.replace(decoded_html, '\n', '')
    # decoded_html = str.replace(decoded_html, 'origin/', '')
    # decoded_html = str.replace(decoded_html, "'", '"')
    # decoded_html = str.replace(decoded_html, 'class=sfera-link sfera-task sfera-link-style',
    #                            'class="sfera-link sfera-task sfera-link-style"')
    # decoded_html = str.replace(decoded_html, '<table border=1 class=dataframe>',
    #                            '<table class="MsoNormalTable" border="1" cellspacing="0" cellpadding="0" width="1440" data-widthmode="wide" data-lastwidth="1761px" style="border-collapse: collapse; width: 1761px;" id="mce_1">')

    decoded_html = str.replace(decoded_html, '<table border=1 class=dataframe>',
                               '<table border=1 style="border-collapse: collapse; width: 1800px;" id="mce_1-1723402032896-98" data-rtc-uid="244a0614-0d0b-42fd-b8af-5992e9fb70be">')
    return decoded_html


def replace_release_html(html, page_id, page_name):
    url1 = sferaUrlKnowledge + 'cid/' + page_id
    response = session.get(url1, verify=False)
    id = json.loads(response.text)['payload']['id']
    data = {
        "id": id,
        "content": html,
        "name": page_name
    }
    url2 =sferaUrlKnowledge2 + '/' + page_id
    response = session.patch(url2, json=data, verify=False)
    if response.ok != True:
        raise Exception("Error creating story " + response)
    return json.loads(response.text)


def generating_release_page(df, page_id, page_name):
    pd.set_option('display.width', 320)
    pd.set_option('display.max_columns', 20)
    np.set_printoptions(linewidth=320)
    print(df)
    # Формируем HTML таблицу
    html = generate_release_html(df)
    print(html)
    replace_release_html(html, page_id, page_name)

page_id = "1490067"
page_name = "ОКР.Библиотеки"
ALL_SERVICE = False

if ALL_SERVICE:
    SERVICE_LST = get_all_service()
    page_id = "1490081"
    page_name = "ОКР.Библиотеки по всем сервисам"


df = get_service_lib_versions()
generating_release_page(df, page_id, page_name)
