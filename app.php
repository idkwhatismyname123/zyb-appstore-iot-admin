<?php
declare(strict_types=1);

session_start();

const DATA_DIR = __DIR__ . DIRECTORY_SEPARATOR . 'data';
const UPLOAD_DIR = __DIR__ . DIRECTORY_SEPARATOR . 'uploads';
const CONFIG_FILE = DATA_DIR . DIRECTORY_SEPARATOR . 'config.json';
const APPS_FILE = DATA_DIR . DIRECTORY_SEPARATOR . 'apps.json';
const SN_FILE = DATA_DIR . DIRECTORY_SEPARATOR . 'sn_access_control.json';
const DEFAULT_ICON_URL = 'https://drive.idkwhatismyname.space/hFxt8p2mnpmLhBS1.png';
const MAX_UPLOAD_SIZE = 1073741824;

function ensureStorage(): void {
    foreach ([DATA_DIR, UPLOAD_DIR] as $directory) {
        if (!is_dir($directory) && !mkdir($directory, 0755, true) && !is_dir($directory)) {
            throw new RuntimeException('无法创建数据目录。');
        }
    }
    loadConfig();
    loadSnConfig();
    loadApps();
}

function readJson(string $path, array $fallback): array {
    if (!is_file($path)) {
        return $fallback;
    }
    $content = file_get_contents($path);
    $data = is_string($content) ? json_decode($content, true) : null;
    return is_array($data) ? $data : $fallback;
}

function writeJson(string $path, array $data): void {
    $result = file_put_contents($path, json_encode($data, JSON_UNESCAPED_UNICODE | JSON_PRETTY_PRINT | JSON_THROW_ON_ERROR), LOCK_EX);
    if ($result === false) {
        throw new RuntimeException('无法写入数据文件。');
    }
}

function loadConfig(): array {
    $initial = [
        'users' => [
            'super_admin' => ['password' => '123456', 'role' => 'super'],
            'manager_user' => ['password' => 'app_manager_123', 'role' => 'manager', 'max_apps' => 10, 'owns_apps' => 0],
        ],
    ];
    if (!is_file(CONFIG_FILE)) {
        writeJson(CONFIG_FILE, $initial);
        return $initial;
    }
    return readJson(CONFIG_FILE, $initial);
}

function saveConfig(array $config): void { writeJson(CONFIG_FILE, $config); }

function loadSnConfig(): array {
    $initial = ['114514' => 'manager_user'];
    if (!is_file(SN_FILE)) {
        writeJson(SN_FILE, $initial);
        return $initial;
    }
    return readJson(SN_FILE, $initial);
}

function saveSnConfig(array $config): void { writeJson(SN_FILE, $config); }

function loadApps(): array {
    $initial = [[
        'appId' => 'mt-001', 'id' => 602750, 'appName' => '114514', 'packageName' => 'com.mt.manager',
        'versionName' => '1.0', 'versionCode' => '1', 'downloadUrl' => '', 'iconUrl' => DEFAULT_ICON_URL,
        'md5' => '114514', 'size' => '259634232', 'updateTime' => (string) nowMs(), 'desc' => '强大的文件管理和编辑工具。',
        'status' => 1, 'category' => '工具', 'publisher' => '个人开发者',
        'tags' => [['name' => '通用', 'bgColor' => '#FFF2D0', 'textColor' => '#C1A161']],
        'version' => '1.0', 'score' => 5.0, 'changelog' => '优化了UI界面，提升了稳定性。', 'enName' => '',
        'allowedSn' => [], 'owner' => 'manager_user',
    ]];
    if (!is_file(APPS_FILE)) {
        writeJson(APPS_FILE, $initial);
        return $initial;
    }
    return array_values(array_filter(readJson(APPS_FILE, []), 'is_array'));
}

function saveApps(array $apps): void { writeJson(APPS_FILE, array_values($apps)); }
function nowMs(): int { return (int) floor(microtime(true) * 1000); }
function h(mixed $value): string { return htmlspecialchars((string) $value, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8'); }
function redirectTo(string $path, array $params = []): never { header('Location: ' . $path . ($params ? '?' . http_build_query($params) : ''), true, 303); exit; }
function jsonResponse(array $data, int $status = 200): never { http_response_code($status); header('Content-Type: application/json; charset=utf-8'); echo json_encode($data, JSON_UNESCAPED_UNICODE); exit; }
function requestPath(): string { return parse_url($_SERVER['REQUEST_URI'] ?? '/', PHP_URL_PATH) ?: '/'; }
function formValue(string $key): string { return trim((string) ($_POST[$key] ?? '')); }

function csrfToken(): string {
    if (empty($_SESSION['csrf'])) { $_SESSION['csrf'] = bin2hex(random_bytes(32)); }
    return $_SESSION['csrf'];
}
function verifyCsrf(): void {
    if (!hash_equals($_SESSION['csrf'] ?? '', (string) ($_POST['csrf'] ?? ''))) {
        http_response_code(419); exit('无效请求，请刷新页面后重试。');
    }
}
function currentUser(): ?string { return isset($_SESSION['user']) ? (string) $_SESSION['user'] : null; }
function requireRole(string $role): string {
    $userName = currentUser();
    $user = $userName ? (loadConfig()['users'][$userName] ?? null) : null;
    if (!$user || (($user['role'] ?? '') !== $role && !(($user['role'] ?? '') === 'super' && $role === 'manager'))) {
        redirectTo('/login', ['next' => requestPath()]);
    }
    return $userName;
}
function flash(string $message, string $type = 'success'): void { $_SESSION['flash'] = ['message' => $message, 'type' => $type]; }
function pullFlash(): ?array { $flash = $_SESSION['flash'] ?? null; unset($_SESSION['flash']); return is_array($flash) ? $flash : null; }
function layout(string $title, string $body): never {
    $flash = pullFlash();
    $alert = $flash ? '<div class="mb-6 rounded-xl border px-4 py-3 ' . ($flash['type'] === 'error' ? 'border-red-200 bg-red-50 text-red-700' : 'border-emerald-200 bg-emerald-50 text-emerald-700') . '">' . h($flash['message']) . '</div>' : '';
    $user = currentUser();
    $nav = $user ? '<div class="flex gap-3 text-sm"><a class="rounded-xl px-3 py-2 text-sky-200 hover:bg-white/10 hover:text-white" href="/manage_app_data_zybiot_1223">应用管理</a><a class="rounded-xl px-3 py-2 text-sky-200 hover:bg-white/10 hover:text-white" href="/super_admin_config_1223">超级管理</a><form method="post" action="/logout"><input type="hidden" name="csrf" value="' . csrfToken() . '"><button class="rounded-xl px-3 py-2 text-slate-300 hover:bg-white/10 hover:text-white">退出 ' . h($user) . '</button></form></div>' : '';
    echo '<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>' . h($title) . '</title><script src="https://cdn.tailwindcss.com"></script><style>body{background:#071221;background-image:radial-gradient(circle at 10% 10%,rgba(14,165,233,.26),transparent 28rem),radial-gradient(circle at 88% 15%,rgba(139,92,246,.26),transparent 26rem),radial-gradient(circle at 50% 100%,rgba(45,212,191,.17),transparent 32rem)}.glass{background:rgba(15,23,42,.58)!important;border:1px solid rgba(255,255,255,.14)!important;box-shadow:0 24px 60px rgba(0,0,0,.28);backdrop-filter:blur(22px)}input,textarea{background:rgba(15,23,42,.48)!important;border-color:rgba(148,163,184,.36)!important;color:#e2e8f0!important}input::placeholder,textarea::placeholder{color:#94a3b8!important}input:focus,textarea:focus{outline:0!important;border-color:#38bdf8!important;box-shadow:0 0 0 3px rgba(56,189,248,.18)!important}table{color:#e2e8f0}thead{background:rgba(148,163,184,.12)!important;color:#cbd5e1!important}.table-row:hover{background:rgba(255,255,255,.05)}button{transition:transform .18s ease,filter .18s ease}button:hover{transform:translateY(-1px);filter:brightness(1.08)}</style></head><body class="min-h-screen text-slate-100"><main class="mx-auto max-w-7xl px-4 py-8"><header class="glass mb-8 flex flex-wrap items-center justify-between gap-4 rounded-3xl px-6 py-5"><a href="/" class="text-xl font-bold tracking-tight text-white">AppStore <span class="text-sky-300">Console</span></a>' . $nav . '</header>' . $alert . $body . '</main></body></html>';
    exit;
}

function filterAppsBySn(array $apps, string $sn): array {
    return array_values(array_filter($apps, static function (array $app) use ($sn): bool {
        $allowed = $app['allowedSn'] ?? null;
        return is_array($allowed) && ($allowed === [] || ($sn !== '' && in_array($sn, $allowed, true)));
    }));
}
function appDetails(array $app): array {
    $size = (int) ($app['size'] ?? 0);
    $sizeStr = $size >= 1048576 ? number_format($size / 1048576, 1) . 'M' : ($size < 1024 ? $size . 'B' : number_format($size / 1024, 1) . 'KB');
    $package = (string) ($app['packageName'] ?? 'com.default.unknown_app');
    return [
        'id' => (int) ($app['id'] ?? random_int(100000, 999999)), 'name' => $app['appName'] ?? '未命名应用', 'enName' => $app['enName'] ?? '',
        'summary' => $app['desc'] ?? '', 'icon' => $app['iconUrl'] ?? DEFAULT_ICON_URL, 'apkUrl' => $app['downloadUrl'] ?? '', 'apkName' => $package,
        'apkSize' => $size, 'apkSizeStr' => $sizeStr, 'apkVersion' => $app['versionName'] ?? $app['version'] ?? '1.0', 'apkMd5' => $app['md5'] ?? '',
        'remark' => $app['desc'] ?? '', 'changeLog' => $app['changelog'] ?? '', 'developer' => $app['publisher'] ?? '', 'uploadTime' => (int) ($app['updateTime'] ?? nowMs()),
        'previewPics' => array_fill(0, 5, $app['iconUrl'] ?? DEFAULT_ICON_URL), 'isSensitive' => 0, 'statusInPad' => 0, 'onShelf' => 1, 'entertainment' => 1,
        'entertainmentLabel' => '轻度娱乐', 'advertisement' => 0, 'advertisementLabel' => '', 'browseWeb' => 0, 'supervise' => 0, 'risk' => 0,
        'browseWebLabel' => '', 'isMonitored' => true, 'type' => 1, 'isCtlWhite' => 1, 'isGreenApp' => 1, 'age' => 8, 'ageLabel' => '8岁+',
        'containPayContent' => 1, 'payContentLabel' => '含三方付费项目', 'icpNumber' => '京ICP备xxxxxx号', 'privacyLink' => '#',
        'permissions' => [['name' => '互联网', 'desc' => '允许应用打开网络套接字。', 'descEng' => 'Allows applications to open network sockets.']],
        'tags' => $app['tags'] ?? [['name' => '通用', 'bgColor' => '#FFF2D0', 'textColor' => '#C1A161']], 'from' => 0, 'remoteInstallMsg' => '', 'appIdThird' => 0,
        'versionCodeThird' => 0, 'extraThird' => '', 'ctl' => 0, 'bizPicture' => '',
    ];
}
function apiSearch(array $apps): never {
    $data = array_map(static function (array $app): array { $m = appDetails($app); return ['apkName' => $m['apkName'], 'ctl' => 0, 'isCtlWhite' => 1, 'isGreenApp' => 1, 'supervise' => 0, 'risk' => 0, 'icon' => $m['icon'], 'id' => $m['id'], 'name' => $m['name'], 'source' => 2, 'size' => $m['apkSize'], 'sizeStr' => $m['apkSizeStr'], 'summary' => $m['summary'], 'version' => $m['apkVersion'], 'type' => 2, 'installNum' => 114514, 'enName' => $m['enName'], 'isEqualKeyword' => 0, 'publishTime' => $m['uploadTime'], 'appIdThird' => 0, 'versionCodeThird' => 0, 'extraThird' => '', 'downloadUrl' => $m['apkUrl']]; }, $apps);
    jsonResponse(['errNo' => 0, 'errMsg' => 'succ', 'cost' => 0.01, 'logId' => (string) nowMs(), 'requestId' => (string) nowMs(), 'data' => $data]);
}

ensureStorage();
$path = requestPath();
$method = $_SERVER['REQUEST_METHOD'] ?? 'GET';

if ($path === '/login' && $method === 'GET') {
    $next = (string) ($_GET['next'] ?? '/manage_app_data_zybiot_1223');
    layout('登录', '<section class="mx-auto max-w-md glass rounded-3xl p-7"><h1 class="mb-6 text-2xl font-bold">后台登录</h1><form method="post" action="/login" class="space-y-4"><input type="hidden" name="csrf" value="' . csrfToken() . '"><input type="hidden" name="next" value="' . h($next) . '"><input class="w-full rounded-lg border p-3" name="username" placeholder="用户名" required><input class="w-full rounded-lg border p-3" type="password" name="password" placeholder="密码" required><button class="w-full rounded-lg bg-gradient-to-r from-sky-500 to-indigo-500 shadow-lg shadow-sky-950/40 px-4 py-3 font-medium text-white hover:from-sky-400 hover:to-indigo-400">登录</button></form></section>');
}
if ($path === '/login' && $method === 'POST') {
    verifyCsrf(); $username = formValue('username'); $password = (string) ($_POST['password'] ?? ''); $user = loadConfig()['users'][$username] ?? null;
    if (!$user || !hash_equals((string) ($user['password'] ?? ''), $password)) { flash('用户名或密码不正确。', 'error'); redirectTo('/login'); }
    session_regenerate_id(true); $_SESSION['user'] = $username; redirectTo(str_starts_with((string) ($_POST['next'] ?? ''), '/') ? (string) $_POST['next'] : '/manage_app_data_zybiot_1223');
}
if ($path === '/logout' && $method === 'POST') { verifyCsrf(); session_destroy(); redirectTo('/'); }
if ($path === '/') { layout('AppStore', '<section class="glass rounded-3xl p-8"><h1 class="text-3xl font-bold">AppStore 模拟后端</h1><p class="mt-3 text-slate-300">PHP 重构版已启用。支持自定义 APK 直链，也可选择本地上传，不依赖 Cloudflare R2。</p><a class="mt-6 inline-block rounded-lg bg-gradient-to-r from-sky-500 to-indigo-500 shadow-lg shadow-sky-950/40 px-5 py-3 font-medium text-white" href="/manage_app_data_zybiot_1223">进入管理后台</a></section>'); }

if ($path === '/manage_app_data_zybiot_1223' && $method === 'GET') {
    $user = requireRole('manager'); $config = loadConfig(); $isSuper = ($config['users'][$user]['role'] ?? '') === 'super'; $rows = '';
    foreach (loadApps() as $app) { $owner = (string) ($app['owner'] ?? '未知'); $allowed = $isSuper || $owner === $user ? (($app['allowedSn'] ?? []) === [] ? '公共' : implode(', ', $app['allowedSn'])) : '权限不足，SN 列表隐藏'; $rows .= '<tr class="table-row border-t border-white/10"><td class="p-3">' . h($app['id'] ?? '') . '</td><td class="p-3 font-medium">' . h($app['appName'] ?? '') . '</td><td class="p-3">' . h($owner) . '</td><td class="p-3">' . h($allowed) . '</td><td class="p-3"><form method="post" action="/manage_app_data_zybiot_1223/delete"><input type="hidden" name="csrf" value="' . csrfToken() . '"><input type="hidden" name="app_id" value="' . h($app['id'] ?? '') . '"><button class="text-red-600 hover:underline">删除</button></form></td></tr>'; }
    $body = '<div class="grid gap-6 lg:grid-cols-2"><section class="glass rounded-3xl p-6"><h1 class="mb-5 text-2xl font-bold">添加应用</h1><p class="mb-5 text-sm text-slate-300">填写自定义直链即可入库；本地上传为可选项，上传后将自动生成本站下载链接。</p><form method="post" action="/manage_app_data_zybiot_1223/add" enctype="multipart/form-data" class="space-y-4"><input type="hidden" name="csrf" value="' . csrfToken() . '"><input class="w-full rounded-lg border p-3" name="appName" placeholder="应用名称" required><input class="w-full rounded-lg border p-3" name="packageName" placeholder="包名" required><input class="w-full rounded-lg border p-3" name="id" placeholder="应用 ID（留空自动生成）"><input class="w-full rounded-lg border p-3" name="downloadUrl" placeholder="APK 自定义直链（上传文件时可留空）"><input class="w-full rounded-lg border p-3" name="iconUrl" value="' . h(DEFAULT_ICON_URL) . '" placeholder="图标链接"><input class="w-full rounded-lg border p-3" name="allowedSn" placeholder="允许的 SN，逗号分隔；留空为公共"><textarea class="w-full rounded-lg border p-3" name="desc" rows="3" placeholder="应用简介"></textarea><label class="block text-sm font-medium">或上传本地 APK（最大 1 GB）<input class="mt-2 block w-full" type="file" name="apk_file" accept=".apk"></label><button class="w-full rounded-lg bg-gradient-to-r from-sky-500 to-indigo-500 shadow-lg shadow-sky-950/40 px-4 py-3 font-medium text-white hover:from-sky-400 hover:to-indigo-400">保存应用</button></form></section><section class="glass overflow-hidden rounded-3xl"><div class="p-6"><h2 class="text-2xl font-bold">应用列表</h2></div><div class="overflow-x-auto"><table class="w-full text-left text-sm"><thead class="bg-white/5 text-slate-300"><tr><th class="p-3">ID</th><th class="p-3">名称</th><th class="p-3">所有者</th><th class="p-3">SN 权限</th><th class="p-3">操作</th></tr></thead><tbody>' . $rows . '</tbody></table></div></section></div>';
    layout('应用管理', $body);
}

if ($path === '/manage_app_data_zybiot_1223/add' && $method === 'POST') {
    $owner = requireRole('manager'); verifyCsrf(); $config = loadConfig(); $userData = $config['users'][$owner]; $apps = loadApps();
    if (($userData['role'] ?? '') === 'manager' && (int) ($userData['owns_apps'] ?? 0) >= (int) ($userData['max_apps'] ?? 9999)) { flash('已达到应用数量限制。', 'error'); redirectTo('/manage_app_data_zybiot_1223'); }
    $name = formValue('appName'); $package = formValue('packageName'); if ($name === '' || $package === '') { flash('应用名称和包名不能为空。', 'error'); redirectTo('/manage_app_data_zybiot_1223'); }
    $downloadUrl = formValue('downloadUrl'); $size = '0'; $md5 = '';
    if (isset($_FILES['apk_file']) && ($_FILES['apk_file']['error'] ?? UPLOAD_ERR_NO_FILE) !== UPLOAD_ERR_NO_FILE) {
        $file = $_FILES['apk_file']; if (($file['error'] ?? UPLOAD_ERR_OK) !== UPLOAD_ERR_OK || (int) ($file['size'] ?? 0) > MAX_UPLOAD_SIZE || !str_ends_with(strtolower((string) ($file['name'] ?? '')), '.apk')) { flash('APK 上传失败，请检查格式或大小。', 'error'); redirectTo('/manage_app_data_zybiot_1223'); }
        $safeName = bin2hex(random_bytes(8)) . '-' . preg_replace('/[^A-Za-z0-9._-]/', '_', basename((string) $file['name'])); $destination = UPLOAD_DIR . DIRECTORY_SEPARATOR . $safeName;
        if (!move_uploaded_file((string) $file['tmp_name'], $destination)) { flash('无法保存上传文件。', 'error'); redirectTo('/manage_app_data_zybiot_1223'); }
        $downloadUrl = '/uploads/' . rawurlencode($safeName); $size = (string) filesize($destination); $md5 = (string) hash_file('md5', $destination);
    }
    if ($downloadUrl === '') { flash('请填写 APK 自定义直链或上传 APK 文件。', 'error'); redirectTo('/manage_app_data_zybiot_1223'); }
    $snList = array_values(array_filter(array_map('trim', explode(',', formValue('allowedSn'))))); foreach ($snList as $sn) { $snOwner = loadSnConfig()[$sn] ?? null; if ($snOwner && $snOwner !== $owner) { flash("您无权使用 SN 码 {$sn}。", 'error'); redirectTo('/manage_app_data_zybiot_1223'); } }
    $idInput = formValue('id'); $id = ctype_digit($idInput) ? (int) $idInput : random_int(100000, 999999); while (in_array($id, array_map(static fn(array $app): int => (int) ($app['id'] ?? 0), $apps), true)) { if ($idInput !== '') { flash('应用 ID 已存在。', 'error'); redirectTo('/manage_app_data_zybiot_1223'); } $id = random_int(100000, 999999); }
    $apps[] = ['appId' => $package . '-' . $id, 'id' => $id, 'appName' => $name, 'packageName' => $package, 'downloadUrl' => $downloadUrl, 'iconUrl' => formValue('iconUrl') ?: DEFAULT_ICON_URL, 'size' => $size, 'md5' => $md5, 'desc' => formValue('desc'), 'owner' => $owner, 'allowedSn' => $snList, 'versionName' => '1.0', 'versionCode' => '1000', 'updateTime' => (string) nowMs(), 'status' => 1, 'category' => '教育', 'publisher' => 'PHP AppStore', 'tags' => [['name' => '通用', 'bgColor' => '#FFF2D0', 'textColor' => '#C1A161']], 'version' => '1.0', 'score' => 5.0, 'changelog' => '首次添加。', 'enName' => '']; saveApps($apps);
    if (($userData['role'] ?? '') === 'manager') { $config['users'][$owner]['owns_apps'] = (int) ($userData['owns_apps'] ?? 0) + 1; saveConfig($config); } flash("应用“{$name}”已保存。"); redirectTo('/manage_app_data_zybiot_1223');
}

if ($path === '/manage_app_data_zybiot_1223/delete' && $method === 'POST') {
    $user = requireRole('manager'); verifyCsrf(); $id = formValue('app_id'); $config = loadConfig(); $apps = loadApps(); $target = null; foreach ($apps as $app) { if ((string) ($app['id'] ?? '') === $id) { $target = $app; break; } } if (!$target || (($target['owner'] ?? '') !== $user && ($config['users'][$user]['role'] ?? '') !== 'super')) { flash('应用不存在或无删除权限。', 'error'); redirectTo('/manage_app_data_zybiot_1223'); } saveApps(array_values(array_filter($apps, static fn(array $app): bool => (string) ($app['id'] ?? '') !== $id))); $owner = $target['owner'] ?? ''; if (($config['users'][$owner]['role'] ?? '') === 'manager') { $config['users'][$owner]['owns_apps'] = max(0, (int) ($config['users'][$owner]['owns_apps'] ?? 1) - 1); saveConfig($config); } flash('应用已删除。'); redirectTo('/manage_app_data_zybiot_1223');
}

if ($path === '/super_admin_config_1223' && $method === 'GET') {
    requireRole('super'); $config = loadConfig(); $users = ''; foreach ($config['users'] as $name => $user) { $limit = ($user['role'] ?? '') === 'manager' ? h($user['owns_apps'] ?? 0) . ' / ' . h($user['max_apps'] ?? '无限制') : '无限制'; $users .= '<tr class="table-row border-t border-white/10"><td class="p-4 font-medium">' . h($name) . '</td><td class="p-4"><span class="rounded-full bg-sky-400/15 px-3 py-1 text-xs text-sky-200">' . h($user['role'] ?? '') . '</span></td><td class="p-4">' . $limit . '</td><td class="p-4"><form method="post" action="/super_admin_config_1223/update_password" class="flex min-w-64 gap-2"><input type="hidden" name="csrf" value="' . csrfToken() . '"><input type="hidden" name="username" value="' . h($name) . '"><input class="min-w-0 flex-1 rounded-xl border px-3 py-2 text-sm" type="password" name="new_password" placeholder="设置新密码" required><button class="rounded-xl bg-white/10 px-3 py-2 text-xs font-medium text-white hover:bg-white/20">更新</button></form></td></tr>'; } $sns = ''; foreach (loadSnConfig() as $sn => $owner) { $sns .= '<tr class="table-row border-t border-white/10"><td class="p-4 font-mono text-sky-200">' . h($sn) . '</td><td class="p-4">' . h($owner) . '</td></tr>'; }
    layout('超级管理', '<section class="glass mb-6 rounded-3xl p-7"><p class="text-sm font-medium uppercase tracking-[.22em] text-sky-300">Control Center</p><h1 class="mt-2 text-3xl font-bold text-white">超级管理</h1><p class="mt-2 text-slate-300">管理后台用户、密码、应用额度和 SN 归属。</p></section><div class="grid gap-6 lg:grid-cols-5"><section class="glass rounded-3xl p-6 lg:col-span-2"><h2 class="mb-2 text-xl font-bold text-white">创建 Manager</h2><p class="mb-5 text-sm text-slate-300">为新的应用管理员配置账号和额度。</p><form method="post" action="/super_admin_config_1223/add_manager" class="space-y-3"><input type="hidden" name="csrf" value="' . csrfToken() . '"><input class="w-full rounded-xl border p-3" name="username" placeholder="用户名" required><input class="w-full rounded-xl border p-3" type="password" name="password" placeholder="初始密码" required><input class="w-full rounded-xl border p-3" name="max_apps" type="number" min="0" value="10"><button class="w-full rounded-xl bg-gradient-to-r from-sky-500 to-indigo-500 px-4 py-3 font-medium text-white">创建用户</button></form><div class="my-7 h-px bg-white/10"></div><h2 class="mb-2 text-xl font-bold text-white">分配 SN</h2><p class="mb-5 text-sm text-slate-300">将指定 SN 的管理权授予一个 Manager。</p><form method="post" action="/super_admin_config_1223/add_sn" class="space-y-3"><input type="hidden" name="csrf" value="' . csrfToken() . '"><input class="w-full rounded-xl border p-3" name="sn" placeholder="SN 码" required><input class="w-full rounded-xl border p-3" name="owner" placeholder="Manager 用户名" required><button class="w-full rounded-xl bg-white/10 px-4 py-3 font-medium text-white hover:bg-white/20">保存 SN 归属</button></form></section><section class="space-y-6 lg:col-span-3"><div class="glass overflow-hidden rounded-3xl"><div class="flex items-center justify-between p-6"><div><h2 class="text-xl font-bold text-white">用户与密码</h2><p class="mt-1 text-sm text-slate-300">可直接为任意后台用户重置密码。</p></div><span class="rounded-full bg-white/10 px-3 py-1 text-sm text-slate-200">' . count($config['users']) . ' 位用户</span></div><div class="overflow-x-auto"><table class="w-full text-left text-sm"><thead><tr><th class="p-4">用户名</th><th class="p-4">角色</th><th class="p-4">应用数量</th><th class="p-4">修改密码</th></tr></thead><tbody>' . $users . '</tbody></table></div></div><div class="glass overflow-hidden rounded-3xl"><div class="p-6"><h2 class="text-xl font-bold text-white">SN 归属</h2><p class="mt-1 text-sm text-slate-300">当前已分配的设备管理权限。</p></div><table class="w-full text-left text-sm"><thead><tr><th class="p-4">SN</th><th class="p-4">所有者</th></tr></thead><tbody>' . $sns . '</tbody></table></div></section></div>');
}
if ($path === '/super_admin_config_1223/add_manager' && $method === 'POST') { requireRole('super'); verifyCsrf(); $config = loadConfig(); $name = formValue('username'); $password = formValue('password'); $limit = filter_var($_POST['max_apps'] ?? 10, FILTER_VALIDATE_INT, ['options' => ['min_range' => 0]]); if ($name === '' || $password === '' || isset($config['users'][$name]) || $limit === false) { flash('用户数据无效或用户名已存在。', 'error'); redirectTo('/super_admin_config_1223'); } $config['users'][$name] = ['password' => $password, 'role' => 'manager', 'max_apps' => $limit, 'owns_apps' => 0]; saveConfig($config); flash('Manager 已创建。'); redirectTo('/super_admin_config_1223'); }
if ($path === '/super_admin_config_1223/update_password' && $method === 'POST') { requireRole('super'); verifyCsrf(); $config = loadConfig(); $name = formValue('username'); $password = formValue('new_password'); if ($name === '' || $password === '' || !isset($config['users'][$name])) { flash('用户或新密码无效。', 'error'); redirectTo('/super_admin_config_1223'); } $config['users'][$name]['password'] = $password; saveConfig($config); flash("用户 {$name} 的密码已更新。"); redirectTo('/super_admin_config_1223'); }
if ($path === '/super_admin_config_1223/add_sn' && $method === 'POST') { requireRole('super'); verifyCsrf(); $sn = formValue('sn'); $owner = formValue('owner'); $users = loadConfig()['users']; if ($sn === '' || ($users[$owner]['role'] ?? '') !== 'manager') { flash('SN 或 Manager 用户无效。', 'error'); redirectTo('/super_admin_config_1223'); } $data = loadSnConfig(); $data[$sn] = $owner; saveSnConfig($data); flash('SN 归属已保存。'); redirectTo('/super_admin_config_1223'); }

if (str_starts_with($path, '/uploads/')) { $file = basename(rawurldecode(substr($path, 9))); $target = UPLOAD_DIR . DIRECTORY_SEPARATOR . $file; if (!is_file($target)) { http_response_code(404); exit('文件不存在'); } header('Content-Type: application/vnd.android.package-archive'); header('Content-Length: ' . filesize($target)); header('Content-Disposition: attachment; filename="' . rawurlencode($file) . '"'); readfile($target); exit; }
if ($path === '/iot-study/appStore/apps') { $sn = trim((string) ($_GET['sn'] ?? '')); $keyword = mb_strtolower(trim((string) ($_GET['keyword'] ?? ''))); $apps = filterAppsBySn(loadApps(), $sn); if ($keyword !== '') { $apps = array_values(array_filter($apps, static fn(array $a): bool => str_contains(mb_strtolower((string) ($a['appName'] ?? '')), $keyword) || str_contains(mb_strtolower((string) ($a['packageName'] ?? '')), $keyword))); } apiSearch($apps); }
if ($path === '/iot-study/appStore/biz/list') { header('Location: /iot-study/appStore/apps' . (!empty($_GET) ? '?' . http_build_query($_GET) : ''), true, 302); exit; }
if ($path === '/iot-study/appStore/apk') { $id = (string) ($_GET['appId'] ?? ''); $apps = loadApps(); $found = null; foreach ($apps as $app) { if ((string) ($app['id'] ?? '') === $id) { $found = $app; break; } } $found ??= $apps[0] ?? null; if (!$found) { jsonResponse(['errNo' => 1000, 'errMsg' => 'App list is empty', 'data' => null]); } $m = appDetails($found); jsonResponse(['errNo' => 0, 'errMsg' => 'succ', 'cost' => 11.45, 'logId' => (string) nowMs(), 'requestId' => (string) nowMs(), 'data' => ['id' => $m['id'], 'apkName' => $m['apkName'], 'version' => $m['apkVersion'], 'url' => $m['apkUrl'], 'size' => $m['apkSize'], 'md5' => $m['apkMd5'], 'patchInfo' => null]]); }
if ($path === '/iot-study/appStore/system/apps' || $path === '/iot-study/appStore/getAutoUpdateList') { apiSearch(loadApps()); }
if ($path === '/iot-study/appStore/recommend/appList') { apiSearch([]); }
if ($path === '/iot-study/appStore/report' || $path === '/iot-study/appStore/installed') { jsonResponse(['errNo' => 0, 'errMsg' => 'succ', 'data' => null]); }
http_response_code(404); layout('未找到页面', '<section class="glass rounded-3xl p-8"><h1 class="text-2xl font-bold">404</h1><p class="mt-2 text-slate-300">请求的页面不存在。</p></section>');
