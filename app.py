# -*- coding: utf-8 -*-
import time
import json
import os
import random
import hashlib
from functools import wraps
from flask import Flask, request, jsonify, redirect, render_template_string, url_for, Response, current_app
from werkzeug.exceptions import RequestEntityTooLarge
import boto3
from botocore.exceptions import NoCredentialsError

# ----------------------
# 全局默认设置
# ----------------------
DEFAULT_ICON_URL = "https://drive.idkwhatismyname.space/hFxt8p2mnpmLhBS1.png"

# ----------------------
# 环境变量及设置
# ----------------------
app = Flask(__name__)
DATA_FILE = "apps.json"
CONFIG_FILE = "config.json"
SN_FILE = "sn_access_control.json"
TEMP_UPLOAD_FOLDER = "temp_uploads"

# 🌟 设置文件上传限制为 1 GB
app.config['MAX_CONTENT_LENGTH'] = 1 * 1024 * 1024 * 1024
app.config['UPLOAD_FOLDER'] = TEMP_UPLOAD_FOLDER

# ----------------------
# 错误处理
# ----------------------
@app.errorhandler(413)
def request_entity_too_large(error):
    """处理文件大小超过 Flask 配置限制 (413 Request Entity Too Large)"""
    return redirect(url_for('admin_page_get', message="错误：文件大小超过 1 GB 的限制，请上传小文件。"))

# ----------------------
# R2 相关配置和初始化
# ----------------------
def get_r2_client():
    """从 config.json 加载 R2 配置并初始化 boto3 客户端"""
    config = load_config()
    r2_config = config.get("r2_config")

    if not r2_config or r2_config.get('access_key_id') == 'YOUR_R2_ACCESS_KEY_ID':
        print("Error: R2 configuration missing or using placeholder values.")
        return None, None

    try:
        s3_client = boto3.client(
            's3',
            endpoint_url=r2_config['endpoint_url'],
            aws_access_key_id=r2_config['access_key_id'],
            aws_secret_access_key=r2_config['secret_access_key']
        )
        return s3_client, r2_config['bucket_name']
    except Exception as e:
        print(f"Error initializing R2 client: {e}")
        return None, None


# ----------------------
# 辅助函数：加载/保存配置 (Config Load/Save)
# ----------------------
def load_config():
    """加载用户配置和全局设置"""
    if not os.path.exists(CONFIG_FILE):
        # 初始配置，包含 R2 模板、用户和公共域名
        initial_config = {
            "public_domain": "zybapk.idkwhatismyname.space",
            "r2_config": {
                "endpoint_url": "https://<ACCOUNT_ID>.r2.cloudflarestorage.com",
                "access_key_id": "YOUR_R2_ACCESS_KEY_ID",
                "secret_access_key": "YOUR_R2_SECRET_ACCESS_KEY",
                "bucket_name": "your-app-store-bucket"
            },
            "users": {
                "super_admin": {"password": "123456", "role": "super"},
                "manager_user": {"password": "app_manager_123", "role": "manager", "max_apps": 10, "owns_apps": 0}
            }
        }
        save_config(initial_config)
        return initial_config

    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"Error reading {CONFIG_FILE}: {e}")
        return {}

def save_config(config):
    """保存用户配置和全局设置"""
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"Error saving {CONFIG_FILE}: {e}")
        return False

def load_sn_config():
    """加载 SN 码归属配置"""
    if not os.path.exists(SN_FILE):
        initial_sn_config = {
            "114514": "manager_user"
        }
        save_sn_config(initial_sn_config)
        return initial_sn_config

    try:
        with open(SN_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"Error reading {SN_FILE}: {e}")
        return {}

def save_sn_config(sn_config):
    """保存 SN 码归属配置"""
    try:
        with open(SN_FILE, "w", encoding="utf-8") as f:
            json.dump(sn_config, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"Error saving {SN_FILE}: {e}")
        return False

# ----------------------
# 权限认证装饰器和函数 (保持不变)
# ----------------------
def get_logged_in_user():
    """从当前请求的 Header 中获取已登录的用户名"""
    auth = request.authorization
    return auth.username if auth else None

def authenticate(realm):
    """要求用户进行身份验证"""
    return Response(
        'Could not verify your access.\n'
        'Login required.', 401,
        {'WWW-Authenticate': f'Basic realm="{realm}"'})

def has_role(required_role):
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            auth = request.authorization
            config = load_config()

            if not auth or auth.username not in config.get("users", {}):
                return authenticate(f"Login as {required_role}")

            user = config["users"][auth.username]

            # 检查密码
            if user["password"] != auth.password:
                return authenticate(f"Login as {required_role}")

            # 检查角色
            user_role = user.get("role", "guest")

            if user_role == "super" and required_role in ("manager", "super"):
                pass
            elif user_role != required_role:
                return Response(f"Access denied. Required role: {required_role}", 403)

            return f(*args, **kwargs)
        return decorated
    return decorator


# ----------------------
# 辅助函数：应用数据 (App Data Utilities)
# ----------------------
def load_apps():
    """加载应用并确保基本结构存在"""
    if not os.path.exists(DATA_FILE):
        # 初始应用列表，确保有 allowedSn 字段
        initial_data = [{
            "appId": "mt-001", "id": 602750, "name": "MT", "appName": "MT管理器",
            "packageName": "com.mt.manager",
            "versionName": "1.0", "versionCode": "1", "downloadUrl": "http://154.9.228.196:8080/static/mt.apk",
            "iconUrl": DEFAULT_ICON_URL,
            "md5": "c783de55addbf3cf3606f825fd784aee",
            "size": "259634232", "updateTime": str(int(time.time() * 1000)), "desc": "强大的文件管理和编辑工具。",
            "status": 1, "category": "工具", "publisher": "个人开发者", "tags": [{"name":"通用","bgColor":"#FFF2D0","textColor":"#C1A161"}],
            "version": "1.0", "score": 5.0, "changelog": "优化了UI界面，提升了稳定性。",
            "enName": "", "allowedSn": [], # 确保默认应用是公共应用
            "owner": "manager_user"
        }]
        save_apps(initial_data)
        return initial_data

    try:
        with open(DATA_FILE, "r", encoding="utf-8", errors='ignore') as f:
            data = json.load(f)
            if not isinstance(data, list): return []
            return [item for item in data if isinstance(item, dict)]

    except json.JSONDecodeError as e:
        # 🌟 修复：如果 JSON 解析失败，打印错误信息，返回空列表，避免程序崩溃。
        print(f"Error reading {DATA_FILE}: JSON Decode Error: {e}. Returning empty list.")
        return []

def save_apps(apps):
    """将应用列表保存到 JSON 文件"""
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(apps, f, ensure_ascii=False, indent=2)

def filter_apps_by_sn(all_apps, client_sn):
    """
    根据客户端 SN 码筛选允许的应用列表，并处理公共应用逻辑。
    V25 强化逻辑：只有明确设置 allowedSn=[] 的应用才是公共应用。
    """
    client_sn = client_sn.strip()

    # 如果客户端提供了 SN 码
    if client_sn:
        filtered_list = []
        for app in all_apps:
            allowed_sns = app.get("allowedSn")

            # 条件：
            # A. allowed_sns 明确为空 [] -> 视为公共应用，可见
            # B. client_sn 存在于 allowed_sns 列表中 -> 视为白名单应用，可见
            if allowed_sns is not None and len(allowed_sns) == 0:
                # 明确的公共应用
                filtered_list.append(app)
            elif allowed_sns and client_sn in allowed_sns:
                # 明确的白名单应用
                filtered_list.append(app)

        return filtered_list

    # 1. 如果客户端未提供 SN 码 (client_sn 为空)
    else:
        # 仅返回 allowedSn 字段明确为空列表 [] 的应用 (即：公共应用)
        return [app for app in all_apps if app.get("allowedSn") is not None and len(app.get("allowedSn")) == 0]


# ----------------------
# 字段映射和 API 适配器 (保持不变)
# ----------------------
DEFAULT_PERMISSIONS = [
    {"name": "互联网", "desc": "允许应用打开网络套接字。", "descEng": "Allows applications to open network sockets."},
    {"name": "读取电话状态", "desc": "允许只读访问电话状态...", "descEng": "Allows read only access to phone state..."}
]

def generate_search_list(app_list):
    search_keywords = ["", "", "期末最强提分秘籍", ""]
    for app_data in app_list:
        search_keywords.append(app_data.get("appName", ""))
    search_keywords.extend([""] * 20)
    return search_keywords

def map_app_fields(app_data):
    """将内部应用结构映射到客户端 App 期望的复杂字段集 (App Detailed Format)"""

    try:
        size_bytes = int(app_data.get("size", 0) or 0)
    except ValueError:
        size_bytes = 0

    size_mb = size_bytes / (1024 * 1024)
    default_preview_pic = app_data.get("iconUrl", DEFAULT_ICON_URL)

    # 修复：确保 packageName 始终存在
    app_package_name = app_data.get("packageName")
    if not app_package_name:
        base_name = app_data.get("appName", app_data.get("name", "unknown_app")).lower().replace(" ", "_")
        app_package_name = f"com.default.{base_name}"

    mapped_app = {
        "id": int(app_data.get("id", random.randint(100000, 999999))),
        "name": app_data.get("appName", app_data.get("name", "未命名应用")),
        "enName": app_data.get("enName", ""),
        "summary": app_data.get("desc", ""),
        "icon": app_data.get("iconUrl", DEFAULT_ICON_URL),
        "apkUrl": app_data.get("downloadUrl", ""),
        "apkName": app_package_name,
        "apkSize": size_bytes,
        "apkSizeStr": f"{size_mb:.1f}M" if size_mb >= 1 else (f"{size_bytes}B" if size_bytes < 1024 else f"{size_bytes/1024:.1f}KB"),
        "apkVersion": app_data.get("versionName", app_data.get("version", "1.0")),
        "apkMd5": app_data.get("md5", ""),
        "remark": app_data.get("desc", ""),
        "changeLog": app_data.get("changelog", ""),
        "developer": app_data.get("publisher", ""),
        "uploadTime": int(app_data.get("updateTime", int(time.time() * 1000))),
        "previewPics": [default_preview_pic] * 5,
        "isSensitive": 0, "statusInPad": 0, "onShelf": 1, "entertainment": 1, "entertainmentLabel": "轻度娱乐",
        "advertisement": 0, "advertisementLabel": "", "browseWeb": 0, "supervise": 0, "risk": 0,
        "browseWebLabel": "", "isMonitored": True, "type": 1, "isCtlWhite": 1, "isGreenApp": 1,
        "age": 8, "ageLabel": "8岁+", "containPayContent": 1, "payContentLabel": "含三方付费项目",
        "icpNumber": "京ICP备xxxxxx号", "privacyLink": "#",
        "permissions": DEFAULT_PERMISSIONS,
        "tags": app_data.get("tags", [{"name":"通用","bgColor":"#FFF2D0","textColor":"#C1A161"}]),
        "from": 0, "remoteInstallMsg": "", "appIdThird": 0, "versionCodeThird": 0, "extraThird": "",
        "ctl": 0, "bizPicture": ""
    }

    return mapped_app

def api_response_search(data_list):
    """适配 /apps, /recommend/appList 等接口 (errNo/data: list)"""
    simplified_data = []

    if data_list:
        for app_data in data_list:
            mapped = map_app_fields(app_data)
            simplified_data.append({
                "apkName": mapped["apkName"], "ctl": mapped["ctl"], "isCtlWhite": mapped["isCtlWhite"],
                "isGreenApp": mapped["isGreenApp"], "supervise": mapped["supervise"], "risk": mapped["risk"],
                "icon": mapped["icon"], "id": mapped["id"], "name": mapped["name"], "source": 2,
                "size": mapped["apkSize"], "sizeStr": mapped["apkSizeStr"], "summary": mapped["summary"],
                "version": mapped["apkVersion"], "type": 2, "installNum": 114514, "enName": mapped["enName"],
                "isEqualKeyword": 0, "publishTime": mapped["uploadTime"], "appIdThird": mapped["appIdThird"],
                "versionCodeThird": mapped["versionCodeThird"], "extraThird": mapped["extraThird"],
                "downloadUrl": mapped["apkUrl"]
            })

    return jsonify({
        "errNo": 0, "errMsg": "succ", "cost": 0.01,
        "logId": f"{int(time.time() * 1000)}", "requestId": f"{int(time.time() * 1000)}",
        "data": simplified_data
    })

def api_response_biz_list(app_list, biz_position):
    """适配 /biz/list 接口 (data: {list: [ { bizName: '...', apps: [...] } ], searchList: [...]})"""

    converted_apps = [map_app_fields(app) for app in app_list]

    biz_list = [
        {
            "bizPosition": biz_position, "bizDisplayType": 1, "bizName": "首页推荐", "bizId": 32,
            "order": 1, "apps": converted_apps
        }
    ]

    return jsonify({
        "errNo": 0, "errMsg": "succ", "cost": 38.65,
        "logId": f"{int(time.time() * 1000)}", "requestId": f"{int(time.time() * 1000)}",
        "data": {
            "list": biz_list,
            "searchList": generate_search_list(app_list)
        }
    })

# ----------------------
# HTML 模板 - App 管理后台 (移除 SN 提示)
# ----------------------
ADMIN_HTML = """
<!DOCTYPE html>
<html lang="zh">
<head>
    <meta charset="UTF-8">
    <title>AppStore 管理面板 - 优化版</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        h1, h2 { color: #333; }
        .container { display: flex; gap: 40px; }
        .list-section, .form-section { flex: 1; min-width: 400px; }
        table { width: 100%; border-collapse: collapse; margin-top: 15px; }
        th, td { border: 1px solid #ddd; padding: 8px; text-align: left; font-size: 14px; word-break: break-all; }
        th { background-color: #f2f2f2; }
        .form-group { margin-bottom: 15px; }
        .form-group label { display: block; margin-bottom: 5px; font-weight: bold; }
        .form-group input[type="text"], .form-group textarea, .form-group input[type="file"] { width: 100%; padding: 8px; box-sizing: border-box; border: 1px solid #ccc; border-radius: 4px; }
        .btn-primary { background-color: #007bff; color: white; padding: 10px 15px; border: none; border-radius: 4px; cursor: pointer; }
        .btn-delete { background-color: #dc3545; color: white; padding: 5px 10px; border: none; border-radius: 4px; cursor: pointer; }
        .msg-success { color: green; font-weight: bold; margin-bottom: 15px; }
        .msg-error { color: red; font-weight: bold; margin-bottom: 15px; }
    </style>
    <script>
        // JS 帮助控制两个表单的显示
        function showUploadForm() {
            document.getElementById('uploadForm').style.display = 'block';
            document.getElementById('addAppForm').style.display = 'none';
        }
        function showAddAppForm() {
            document.getElementById('uploadForm').style.display = 'none';
            document.getElementById('addAppForm').style.display = 'block';
        }
    </script>
</head>
<body>
    <h1>AppStore 模拟后端管理面板 - 优化版</h1>
    {% if message %}
        <p class="{% if '错误' in message %}msg-error{% else %}msg-success{% endif %}">{{ message }}</p>
    {% endif %}

    <div class="container">

        <div class="form-section">
            <h2>应用上传与添加</h2>
            <p>
                <button onclick="showUploadForm()">1. 上传 APK 到 R2</button>
                <button onclick="showAddAppForm()">2. 添加应用信息</button>
            </p>

            <div id="uploadForm" style="display: block;">
                <h3>1. 上传 APK 到 Cloudflare R2 (最大 1 GB)</h3>
                <form method="POST" action="{{ url_for('upload_apk') }}" enctype="multipart/form-data">
                    <div class="form-group">
                        <label for="apkFile">选择 APK 文件</label>
                        <input type="file" id="apkFile" name="apk_file" accept=".apk" required>
                    </div>
                    <button type="submit" class="btn-primary">上传并获取信息</button>
                </form>
                <p style="margin-top: 10px; color: gray;">上传成功后，文件信息将自动填充到下面的表单。</p>
            </div>

            <div id="addAppForm" style="display: none;">
                <h3>2. 添加入库信息</h3>
                <form method="POST" action="{{ url_for('add_app') }}">
                    <input type="hidden" id="downloadUrl_hidden" name="downloadUrl_hidden">
                    <input type="hidden" id="size_hidden" name="size_hidden">
                    <input type="hidden" id="md5_hidden" name="md5_hidden">

                    <div class="form-group">
                        <label for="appName">应用名称</label>
                        <input type="text" id="appName" name="appName" required>
                    </div>
                    <div class="form-group">
                        <label for="packageName">包名</label>
                        <input type="text" id="packageName" name="packageName" required>
                    </div>
                    <div class="form-group">
                        <label for="id">应用 ID</label>
                        <input type="text" id="id" name="id">
                    </div>
                    <div class="form-group">
                        <label>APK 下载链接 (R2)</label>
                        <input type="text" id="downloadUrl_display" value="上传后自动填充" disabled>
                    </div>
                    <div class="form-group">
                        <label for="iconUrl">图标链接</label>
                        <input type="text" id="iconUrl" name="iconUrl" value="{{ DEFAULT_ICON_URL }}" required>
                    </div>
                    <div class="form-group">
                        <label>APK 大小 (字节)</label>
                        <input type="text" id="size_display" value="上传后自动填充" disabled>
                    </div>
                    <div class="form-group">
                        <label>MD5 校验码</label>
                        <input type="text" id="md5_display" value="上传后自动填充" disabled>
                    </div>

                    <div class="form-group">
                        <label for="allowedSn">允许的 SN 码 (您必须拥有该 SN 的管理权)</label>
                        <textarea id="allowedSn" name="allowedSn" rows="3"></textarea>
                    </div>
                    <div class="form-group">
                        <label for="desc">应用简介</label>
                        <textarea id="desc" name="desc" rows="3"></textarea>
                    </div>
                    <button type="submit" class="btn-primary">添加到 AppStore</button>
                </form>
            </div>
        </div>

        <div class="list-section">
            <h2>现有应用列表</h2>
            <table>
                <thead>
                    <tr>
                        <th>ID</th>
                        <th>名称</th>
                        <th>MD5</th>
                        <th>所有者</th>
                        <th>SN 权限</th>
                        <th>操作</th>
                    </tr>
                </thead>
                <tbody>
                    {% for app in apps_list %}
                    <tr>
                        <td>{{ app.id }}</td>
                        <td>{{ app.appName }}</td>
                        <td>{{ app.md5[:10] }}...</td>
                        <td>{{ app.owner }}</td>
                        <td>
                            {% if app.allowedSn and app.allowedSn|length > 0 and app.allowedSn|first != '(权限不足，SN列表隐藏)' %}
                                {{ app.allowedSn | join(', ') }}
                            {% elif app.allowedSn and app.allowedSn|first == '(权限不足，SN列表隐藏)' %}
                                (权限不足，SN列表隐藏)
                            {% else %}
                                (无限制/公共)
                            {% endif %}
                        </td>
                        <td>
                            <form method="POST" action="{{ url_for('delete_app') }}" style="display:inline;">
                                <input type="hidden" name="app_id_to_delete" value="{{ app.id }}">
                                <button type="submit" class="btn-delete" onclick="return confirm('确定要删除应用 {{ app.appName }} 吗？');">删除</button>
                            </form>
                        </td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>

    </div>
    {% if uploaded_info %}
    <script>
        // 上传成功后自动填充表单
        document.getElementById('downloadUrl_hidden').value = "{{ uploaded_info.downloadUrl }}";
        document.getElementById('size_hidden').value = "{{ uploaded_info.size }}";
        document.getElementById('md5_hidden').value = "{{ uploaded_info.md5 }}";

        document.getElementById('downloadUrl_display').value = "{{ uploaded_info.downloadUrl }}";
        document.getElementById('size_display').value = "{{ uploaded_info.size }}";
        document.getElementById('md5_display').value = "{{ uploaded_info.md5 }}";

        // 尝试自动填充包名和应用名
        document.getElementById('packageName').value = "{{ uploaded_info.packageName | default('') }}";
        document.getElementById('appName').value = "{{ uploaded_info.appName | default('') }}";
        // 切换到添加应用表单
        showAddAppForm();
    </script>
    {% endif %}
</body>
</html>
"""

# HTML 模板 - 用于 / 首页 (V21 核心修改，保持不变)
INDEX_HTML = """
<!DOCTYPE html>
<html lang="zh">
<head>
    <meta charset="UTF-8">
    <title>测试成功</title>
    <style>
        body { margin: 0; display: flex; justify-content: center; align-items: center; height: 100vh; font-family: Arial, sans-serif; background-color: #f0f0f0; }
        h1 { color: #28a745; font-size: 48px; }
    </style>
</head>
<body>
    <h1>测试成功 ✅</h1>
</body>
</html>
"""

# HTML 模板 - 超级管理员后台 (Super Admin) (保持不变)
SUPER_ADMIN_HTML = """
<!DOCTYPE html>
<html lang="zh">
<head>
    <meta charset="UTF-8">
    <title>超级管理员后台由idkwhatismyname创建</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        h1, h2 { color: #333; }
        .user-box, .sn-box { border: 1px solid #ccc; padding: 20px; margin-bottom: 20px; border-radius: 5px; }
        table { width: 100%; border-collapse: collapse; margin-top: 10px; }
        th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
        .form-group { margin-bottom: 15px; }
        .form-group label { display: block; margin-bottom: 5px; font-weight: bold; }
        .form-group input[type="text"], .form-group input[type="number"], .form-group select { padding: 8px; border: 1px solid #ccc; border-radius: 4px; }
        .btn { padding: 10px 15px; background-color: #4CAF50; color: white; border: none; border-radius: 4px; cursor: pointer; }
        .btn-delete { background-color: #dc3545; color: white; padding: 5px 10px; border: none; border-radius: 4px; cursor: pointer; }
        .msg-success { color: green; font-weight: bold; }
        .msg-error { color: red; font-weight: bold; }
    </style>
</head>
<body>
    <h1>超级管理员配置</h1>
    {% if message %}
        <p class="{% if '错误' in message %}msg-error{% else %}msg-success{% endif %}">{{ message }}</p>
    {% endif %}

    <div class="user-box">
        <h2>后台用户管理 (Manager)</h2>
        <table>
            <thead>
                <tr>
                    <th>用户名</th>
                    <th>角色</th>
                    <th>当前应用数</th>
                    <th>最大应用限制</th>
                    <th>操作</th>
                </tr>
            </thead>
            <tbody>
                {% for username, user in config.users.items() %}
                <tr>
                    <td>{{ username }}</td>
                    <td>{{ user.role }}</td>
                    <td>{% if user.role == 'manager' %}{{ user.owns_apps | default(0) }}{% else %}N/A{% endif %}</td>
                    <td>{% if user.role == 'manager' %}{{ user.max_apps | default('无限制') }}{% else %}N/A{% endif %}</td>
                    <td>
                        {% if user.role == 'manager' %}
                            <form method="POST" action="{{ url_for('update_user_config', username=username) }}" style="display:inline;">
                                <input type="text" name="new_password" placeholder="设置新密码">
                                <input type="number" name="new_max_apps" placeholder="设置应用上限" value="{{ user.max_apps | default(10) }}" min="0" required>
                                <button type="submit">更新配置</button>
                            </form>
                        {% elif user.role == 'super' %}
                            (超级管理员)
                        {% endif %}
                    </td>
                </tr>
                {% endfor %}
            </tbody>
        </table>

        <h3>添加新 Manager 用户</h3>
        <form method="POST" action="{{ url_for('add_new_manager') }}">
            <div class="form-group">
                <input type="text" name="new_username" placeholder="用户名 (如：manager_C)" required>
                <input type="text" name="new_password" placeholder="初始密码" required>
                <input type="number" name="new_max_apps" placeholder="最大应用数限制 (默认10)" value="10" min="0" required>
            </div>
            <button type="submit" class="btn">添加 Manager</button>
        </form>
    </div>

    <div class="sn-box">
        <h2>SN 码权限管理 (分配/解除所有者)</h2>
        <form method="POST" action="{{ url_for('add_sn_owner') }}">
            <div class="form-group">
                <label for="sn_code">SN 码:</label>
                <input type="text" id="sn_code" name="sn_code" placeholder="输入 SN 码" required>
            </div>
            <div class="form-group">
                <label for="sn_owner">指定所有者 (Manager):</label>
                <select id="sn_owner" name="sn_owner" required>
                    {% for username, user in config.users.items() %}
                        {% if user.role == 'manager' %}
                            <option value="{{ username }}">{{ username }}</option>
                        {% endif %}
                    {% endfor %}
                </select>
            </div>
            <button type="submit" class="btn">添加/修改 SN 码所有者</button>
        </form>

        <h3 style="margin-top: 20px;">当前 SN 码归属列表</h3>
        <table>
            <thead>
                <tr><th>SN 码</th><th>所有者</th><th>操作</th></tr>
            </thead>
            <tbody>
                {% for sn, owner in sn_config.items() %}
                <tr>
                    <td>{{ sn }}</td>
                    <td>{{ owner }}</td>
                    <td>
                        <form method="POST" action="{{ url_for('delete_sn_owner') }}" style="display:inline;">
                            <input type="hidden" name="sn_code_to_delete" value="{{ sn }}">
                            <button type="submit" class="btn-delete" onclick="return confirm('确定要解除 SN 码 {{ sn }} 的归属绑定吗？');">解除绑定</button>
                        </form>
                    </td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
    </div>

    <p><a href="{{ url_for('admin_page_get') }}">返回应用管理后台</a></p>
</body>
</html>
"""

# ----------------------
# 路由定义 (App Management Routes - Manager Role)
# ----------------------

@app.route("/")
def index(): return render_template_string(INDEX_HTML)

# 路由：管理面板 - GET (Manager 权限)
@app.route("/manage_app_data_zybiot_1223", methods=["GET"])
@has_role("manager")
def admin_page_get():
    message = request.args.get('message')
    apps_list = load_apps()

    logged_in_user = get_logged_in_user()
    config = load_config()
    user_role = config["users"].get(logged_in_user, {}).get("role")

    display_list = []
    for app in apps_list:
        app_owner = app.get('owner', '未知')
        can_see_sn = (user_role == "super" or app_owner == logged_in_user)

        display_app = app.copy()
        display_app['id'] = str(app.get('id'))
        display_app['owner'] = app_owner

        # 优化管理后台显示：如果是空列表，显示 (无限制/公共)
        display_app['allowedSn'] = app.get('allowedSn', [])
        if display_app['allowedSn'] is None or len(display_app['allowedSn']) == 0:
             display_app['allowedSn'] = ["(无限制/公共)"]

        if not can_see_sn:
            display_app['allowedSn'] = ["(权限不足，SN列表隐藏)"]

        display_list.append(display_app)

    uploaded_info = request.args.to_dict()

    # 将 DEFAULT_ICON_URL 传递给模板
    return render_template_string(ADMIN_HTML, apps_list=display_list, message=message, uploaded_info=uploaded_info, DEFAULT_ICON_URL=DEFAULT_ICON_URL)


# 🌟 路由：APK 文件上传 (到 R2)
@app.route("/manage_app_data_zybiot_1223/upload_apk", methods=["POST"])
@has_role("manager")
def upload_apk():
    # 文件大小已经在 @app.errorhandler(413) 中处理

    if 'apk_file' not in request.files:
        return redirect(url_for('admin_page_get', message="错误：未选择文件！"))

    file = request.files['apk_file']
    if file.filename == '':
        return redirect(url_for('admin_page_get', message="错误：文件名为空！"))

    s3_client, bucket_name = get_r2_client()
    if not s3_client:
         return redirect(url_for('admin_page_get', message="错误：R2 配置失败，请检查 config.json。"))

    # 1. 临时保存文件以计算 MD5 和大小
    filename = file.filename
    temp_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)

    try:
        file.save(temp_path)
    except Exception as e:
        return redirect(url_for('admin_page_get', message=f"错误：本地保存文件失败: {e}"))

    file_size = os.path.getsize(temp_path)

    # 2. 自动计算 MD5
    hash_md5 = hashlib.md5()
    with open(temp_path, "rb") as f:
        # 使用更安全的内存高效方式计算大文件的 MD5
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    file_md5 = hash_md5.hexdigest()

    # 3. 上传到 R2
    try:
        s3_client.upload_file(temp_path, bucket_name, filename, ExtraArgs={'ContentType': 'application/vnd.android.package-archive'})

        # 4. 删除本地临时文件
        os.remove(temp_path)

        # 5. 生成下载 URL
        config = load_config()
        public_domain = config.get('public_domain', 'default-download-domain.com')
        download_url = f"https://{public_domain}/{filename}"

        # 6. 重定向到添加应用表单，并传递信息
        return redirect(url_for(
            'admin_page_get',
            message=f"文件 {filename} 上传 R2 成功。",
            downloadUrl=download_url,
            size=file_size,
            md5=file_md5,
            packageName=filename.replace(".apk", "").split("_")[-1],
            appName=filename.replace(".apk", "").replace("_", " ")
        ))

    except NoCredentialsError:
        if os.path.exists(temp_path): os.remove(temp_path)
        return redirect(url_for('admin_page_get', message="错误：R2 凭证缺失或无效。"))
    except Exception as e:
        if os.path.exists(temp_path): os.remove(temp_path)
        return redirect(url_for('admin_page_get', message=f"错误：上传 R2 失败: {e}"))


# 路由：添加应用逻辑 (Manager 权限 - 从 R2 链接入库)
@app.route("/manage_app_data_zybiot_1223/add", methods=["POST"])
@has_role("manager")
def add_app():
    owner_user = get_logged_in_user()
    config = load_config()
    sn_config = load_sn_config()
    all_apps = load_apps()
    user_data = config["users"].get(owner_user, {})
    data = request.form

    # 核心字段现在通过隐藏字段传递
    download_url = data.get("downloadUrl_hidden")
    file_size = data.get("size_hidden")
    file_md5 = data.get("md5_hidden")

    # 1. 检查文件信息是否完整
    if not all([download_url, file_size, file_md5]):
        return redirect(url_for('admin_page_get', message="错误：请先上传 APK 文件并获取 MD5/大小信息！"))

    # 2. 检查应用数量限制 (逻辑保持不变)
    if user_data.get("role") == "manager":
        current_owns = user_data.get("owns_apps", 0)
        max_limit = user_data.get("max_apps", 9999)
        if current_owns >= max_limit:
            return redirect(url_for('admin_page_get', message=f"错误：已达到应用数量限制 ({max_limit} 个)。"))

    # 3. 检查 SN 码的白名单权限 (逻辑保持不变)
    allowed_sn_raw = data.get("allowedSn", "").strip()
    if allowed_sn_raw:
        sn_list = [sn.strip() for sn in allowed_sn_raw.split(',') if sn.strip()]
        for sn in sn_list:
            sn_owner = sn_config.get(sn)
            if sn_owner and sn_owner != owner_user:
                return redirect(url_for('admin_page_get', message=f"错误：SN 码 {sn} 已被用户 {sn_owner} 管理，您无权为其添加应用。"))
        app_data_allowed_sn = sn_list
    else:
        app_data_allowed_sn = []

    # 4. 继续处理应用数据 (使用 R2 提供的 MD5/Size)
    required_fields = ["appName", "packageName"] # 其他字段已由上传提供
    if not all(data.get(k) for k in required_fields):
        return redirect(url_for('admin_page_get', message="错误：应用名称和包名不能为空！"))

    app_id_raw = data.get("id").strip()
    if app_id_raw and app_id_raw.isdigit():
        new_id = int(app_id_raw)
    else:
        new_id = random.randint(100000, 999999)

    app_data = {
        "appId": data.get("packageName", "") + "-" + str(new_id),
        "id": new_id,
        "appName": data.get("appName", "新应用"),
        "packageName": data.get("packageName", "com.new.app"),
        "downloadUrl": download_url, # 来自 R2
        "iconUrl": data.get("iconUrl", DEFAULT_ICON_URL),
        "size": file_size, # 来自 R2
        "md5": file_md5, # 来自 R2
        "desc": data.get("desc", ""),
        "owner": owner_user,
        "allowedSn": app_data_allowed_sn,

        "versionName": "1.0", "versionCode": "1000", "updateTime": str(int(time.time() * 1000)),
        "status": 1, "category": "教育", "publisher": "由idkwhatismyname创建",
        "tags": [{"name":"通用","bgColor":"#FFF2D0","textColor":"#C1A161"}], "version": "1.0", "score": 5.0, "changelog": "首次添加。", "enName": "",
    }

    if any(app.get("id") == app_data["id"] for app in all_apps):
        if not app_id_raw: app_data["id"] = random.randint(100000, 999999)
        else: return redirect(url_for('admin_page_get', message=f"错误：应用 ID {app_data['id']} 已存在！请换一个 ID。"))

    all_apps.append(app_data)
    save_apps(all_apps)

    # 5. 更新管理员的应用计数
    if user_data.get("role") == "manager":
        config["users"][owner_user]["owns_apps"] = current_owns + 1
        save_config(config)

    return redirect(url_for('admin_page_get', message=f"应用 '{app_data['appName']}' 添加成功！ID: {app_data['id']}"))


# 路由：删除应用功能 (Manager 权限 - 保持不变)
@app.route("/manage_app_data_zybiot_1223/delete", methods=["POST"])
@has_role("manager")
def delete_app():
    owner_user = get_logged_in_user()
    app_id_to_delete = request.form.get("app_id_to_delete")
    if not app_id_to_delete:
        return redirect(url_for('admin_page_get', message="错误：未提供应用 ID"))

    all_apps = load_apps()
    original_count = len(all_apps)

    app_to_delete = next((app for app in all_apps if str(app.get("id")) == app_id_to_delete), None)

    # 检查权限：只有应用的拥有者或 Super Admin 才能删除
    user_role = load_config()["users"].get(owner_user, {}).get("role")

    if app_to_delete and app_to_delete.get('owner') != owner_user and user_role != "super":
        return redirect(url_for('admin_page_get', message="错误：您无权删除此应用。"))

    new_apps_list = [app for app in all_apps if str(app.get("id")) != app_id_to_delete]

    if len(new_apps_list) < original_count:
        save_apps(new_apps_list)
        msg = f"应用 ID {app_id_to_delete} 删除成功。"

        # 减少管理员的应用计数
        app_owner = app_to_delete.get('owner')
        config = load_config()
        if app_owner in config["users"] and config["users"][app_owner].get("role") == "manager":
            config["users"][app_owner]["owns_apps"] = max(0, config["users"][app_owner].get("owns_apps", 1) - 1)
            save_config(config)

    else:
        msg = f"应用 ID {app_id_to_delete} 未找到，删除失败。"

    return redirect(url_for('admin_page_get', message=msg))


# 路由：超级管理员后台 - GET (Super 权限)
@app.route("/super_admin_config_1223", methods=["GET"])
@has_role("super")
def super_admin_page():
    config = load_config()
    sn_config = load_sn_config()
    message = request.args.get('message')
    return render_template_string(SUPER_ADMIN_HTML, config=config, sn_config=sn_config, message=message)

# 路由：超级管理员后台 - 更新用户配置 (Super 权限)
@app.route("/super_admin_config_1223/update_user/<username>", methods=["POST"])
@has_role("super")
def update_user_config(username):
    config = load_config()
    new_password = request.form.get("new_password")
    new_max_apps = request.form.get("new_max_apps")

    if username not in config["users"] or config["users"][username].get("role") != "manager":
        return redirect(url_for('super_admin_page', message="错误：用户不存在或无 manager 权限。"))

    user = config["users"][username]

    # 更新密码
    if new_password:
        user["password"] = new_password

    # 更新应用限制
    try:
        max_apps = int(new_max_apps)
        if max_apps < user.get("owns_apps", 0):
            return redirect(url_for('super_admin_page', message=f"错误：最大应用数 ({max_apps}) 不能低于当前已安装应用数 ({user.get('owns_apps', 0)})。"))
        if max_apps < 0: raise ValueError
        user["max_apps"] = max_apps
    except ValueError:
        return redirect(url_for('super_admin_page', message="错误：最大应用数必须是有效数字。"))

    save_config(config)
    return redirect(url_for('super_admin_page', message=f"用户 {username} 的配置已成功更新。"))

# 路由：超级管理员后台 - 添加新用户 (Super 权限)
@app.route("/super_admin_config_1223/add_manager", methods=["POST"])
@has_role("super")
def add_new_manager():
    config = load_config()
    new_username = request.form.get("new_username")
    new_password = request.form.get("new_password")
    new_max_apps = request.form.get("new_max_apps", 10)

    if new_username in config["users"]:
        return redirect(url_for('super_admin_page', message=f"错误：用户名 {new_username} 已存在。"))

    if not new_username or not new_password:
        return redirect(url_for('super_admin_page', message="错误：用户名和密码不能为空。"))

    try:
        max_apps = int(new_max_apps)
        if max_apps < 0: raise ValueError
    except ValueError:
        return redirect(url_for('super_admin_page', message="错误：最大应用数必须是有效数字。"))

    config["users"][new_username] = {
        "password": new_password,
        "role": "manager",
        "max_apps": max_apps,
        "owns_apps": 0
    }

    save_config(config)
    return redirect(url_for('super_admin_page', message=f"用户 {new_username} (Manager) 添加成功，最大应用数限制为 {max_apps}。"))

# 路由：超级管理员后台 - SN 码所有者分配 (V12 核心新增)
@app.route("/super_admin_config_1223/add_sn_owner", methods=["POST"])
@has_role("super")
def add_sn_owner():
    sn_code = request.form.get("sn_code").strip()
    sn_owner = request.form.get("sn_owner").strip()
    sn_config = load_sn_config()
    config = load_config()

    if not sn_code or not sn_owner:
        return redirect(url_for('super_admin_page', message="错误：SN 码和所有者不能为空。"))

    if sn_owner not in config["users"] or config["users"][sn_owner].get("role") != "manager":
        return redirect(url_for('super_admin_page', message=f"错误：用户 {sn_owner} 不是有效的 Manager。"))

    sn_config[sn_code] = sn_owner
    save_sn_config(sn_config)

    return redirect(url_for('super_admin_page', message=f"SN 码 {sn_code} 已成功分配给 {sn_owner}。"))

# 🌟 新增路由：超级管理员解除 SN 归属绑定 (V19)
@app.route("/super_admin_config_1223/delete_sn_owner", methods=["POST"])
@has_role("super")
def delete_sn_owner():
    sn_code_to_delete = request.form.get("sn_code_to_delete")
    sn_config = load_sn_config()

    if sn_code_to_delete in sn_config:
        del sn_config[sn_code_to_delete]
        save_sn_config(sn_config)
        return redirect(url_for('super_admin_page', message=f"SN 码 {sn_code_to_delete} 的归属绑定已成功解除。"))
    else:
        return redirect(url_for('super_admin_page', message=f"错误：SN 码 {sn_code_to_delete} 未找到或未绑定所有者。"))


# 路由：核心 API (SN 筛选等 - 保持不变)
@app.route("/iot-study/appStore/apps", methods=["GET"])
def list_and_search_apps():
    client_sn = request.args.get("sn", "").strip()
    all_apps = load_apps()
    filtered_apps = filter_apps_by_sn(all_apps, client_sn)
    keyword = request.args.get("keyword", "").strip()
    if not keyword: results = filtered_apps
    else:
        search_lower = keyword.lower()
        results = [app_data for app_data in filtered_apps if search_lower in app_data.get("appName", "").lower() or search_lower in app_data.get("packageName", "").lower()]
    return api_response_search(results)

# 🌟 V28 核心修改：强制重定向 biz/list 到 apps (处理客户端硬编码/缓存)
@app.route("/iot-study/appStore/biz/list", methods=["GET", "POST"])
def biz_list_apps():
    # 🌟 将所有 URL 参数收集起来
    args = request.args.to_dict()
    # 🌟 构建新的 URL，重定向到 /apps 接口，并携带所有原始参数
    redirect_url = url_for('list_and_search_apps', **args)
    # 🌟 返回 302 重定向，强制客户端 App 使用 /apps 接口
    return redirect(redirect_url, code=302)


@app.route("/iot-study/appStore/apk", methods=["GET"])
def apk_details():
    app_id = request.args.get("appId")
    all_apps = load_apps()

    found_app = next((app_data for app_data in all_apps if str(app_data.get("id")) == str(app_id)), None)

    if not found_app:
        if all_apps: found_app = all_apps[0]
        else: return jsonify({"errNo": 1000, "errMsg": "App list is empty", "data": None})

    mapped_app = map_app_fields(found_app)
    apk_data = {"id": mapped_app["id"], "apkName": mapped_app["apkName"], "version": mapped_app["apkVersion"], "url": mapped_app["apkUrl"], "size": mapped_app["apkSize"], "md5": mapped_app["apkMd5"], "patchInfo": None}

    return jsonify({"errNo": 0, "errMsg": "succ", "cost": 11.45, "logId": f"{int(time.time() * 1000)}", "requestId": f"{int(time.time() * 1000)}", "data": apk_data})

@app.route("/iot-study/appStore/system/apps", methods=["GET"])
def system_apps_list(): return api_response_search(load_apps())
@app.route("/iot-study/appStore/getAutoUpdateList", methods=["POST"])
def auto_update_list(): return api_response_search(load_apps())

@app.route("/iot-study/appStore/recommend/appList", methods=["POST"])
def recommend_app_list(): return api_response_search([]) # 强制返回空列表
@app.route("/iot-study/appStore/report", methods=["POST"])
def app_report(): return jsonify({"errNo": 0, "errMsg": "succ", "data": None})
@app.route("/iot-study/appStore/installed", methods=["POST", "GET"])
def app_installed(): return jsonify({"errNo": 0, "errMsg": "succ", "data": None})


# ----------------------
# 启动应用
# ----------------------
if __name__ == "__main__":
    print("AppStore Backend started.")
    print(f"Super Admin URL: http://127.0.0.1:8080/super_admin_config_1223 (User: super_admin, Pass: 123456)")
    print("Manager URL: http://127.0.0.1:8080/manage_app_data_zybiot_1223 (Requires Manager Login)")
    print("代码由idkwhatismyname编写")
    print(f"加一下q群吧104578605")
  

    # 修复启动时的应用上下文问题
    with app.app_context():
        if not os.path.exists(app.config['UPLOAD_FOLDER']):
            os.makedirs(app.config['UPLOAD_FOLDER'])
        # 确保配置文件存在并初始化
        if not os.path.exists(CONFIG_FILE):
            load_config()
        if not os.path.exists(SN_FILE):
            load_sn_config()

    app.run(host="0.0.0.0", port=8080, debug=True)
