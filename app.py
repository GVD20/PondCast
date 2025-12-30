import os
import sys
import socket
import threading
import webbrowser
import time
import logging
import collections
import json
import argparse
import random
from datetime import datetime, timedelta
from flask import Flask, render_template_string, request, send_from_directory, jsonify, abort

# ================= 项目打包辅助 =================
def resource_path(relative_path):
    """获取资源的绝对路径，兼容开发环境和 PyInstaller 打包环境"""
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

# ================= 配置加载逻辑 =================
DEFAULT_CONFIG = {
    "port": 8000,
    "release_dir": "release",
    "received_dir": "received"
}

def load_config():
    """优先级：命令行参数 > 配置文件 > 默认值"""
    # 1. 解析命令行参数
    parser = argparse.ArgumentParser(description="PondCast - 局域网文件池")
    parser.add_argument('--port', type=int, help='指定服务端口')
    parser.add_argument('--config', type=str, default='config.json', help='指定配置文件路径')
    args = parser.parse_args()

    # 2. 加载配置文件 (如果存在)
    config = DEFAULT_CONFIG.copy()
    config_path = args.config
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                file_config = json.load(f)
                config.update(file_config)
                print(f"[Info] 已加载配置文件: {config_path}")
        except Exception as e:
            print(f"[Warn] 配置文件加载失败: {e}")

    # 3. 命令行参数覆盖
    if args.port:
        config['port'] = args.port

    return config

CONFIG = load_config()
RELEASE_DIR = CONFIG['release_dir']
RECEIVED_DIR = CONFIG['received_dir']
MAX_EVENTS = 50 

# 禁止输出 Flask 的常规日志
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

app = Flask(__name__)

# 全局状态
SERVER_STATE = {
    'locked': False,
    'file_pool': False,
    'current_port': CONFIG['port']
}

# 活跃节点追踪
ACTIVE_PEERS = {}
PEER_TIMEOUT = 8 
EVENT_LOG = collections.deque(maxlen=MAX_EVENTS)
LAST_ONLINE_IPS = set()

# ================= 核心逻辑工具 =================

def ensure_directories():
    if not os.path.exists(RELEASE_DIR): os.makedirs(RELEASE_DIR)
    if not os.path.exists(RECEIVED_DIR): os.makedirs(RECEIVED_DIR)

def get_local_ips():
    ip_list = []
    try:
        hostname = socket.gethostname()
        for ip in socket.gethostbyname_ex(hostname)[2]:
            if not ip.startswith("127."): ip_list.append(ip)
    except:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip_list.append(s.getsockname()[0])
            s.close()
        except: pass
    return ip_list

def is_port_in_use(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('127.0.0.1', port)) == 0

def find_available_port(start_port):
    """如果指定端口占用，自动切换到 20000-60000 随机端口"""
    if not is_port_in_use(start_port):
        return start_port
    
    print(f"[Warn] 端口 {start_port} 被占用，正在寻找随机可用端口...")
    for _ in range(100): # 尝试100次
        random_port = random.randint(20000, 60000)
        if not is_port_in_use(random_port):
            return random_port
    raise RuntimeError("无法找到可用端口")

def is_local_admin():
    sender_ip = request.remote_addr
    return sender_ip == '127.0.0.1' or sender_ip == 'localhost'

def get_device_type(user_agent):
    ua = str(user_agent).lower()
    if 'android' in ua or 'iphone' in ua or 'ipad' in ua or 'mobile' in ua:
        return 'mobile'
    return 'desktop'

def get_masked_name(filename):
    if not filename: return "***"
    try:
        name, ext = os.path.splitext(filename)
        if len(name) <= 2: return name + "***" + ext
        return name[:2] + "***" + ext
    except:
        return "***" + filename[-4:] if len(filename) > 4 else "***"

def add_event(type, msg, ip=None, filename=None):
    EVENT_LOG.appendleft({
        'id': int(time.time() * 1000000), 
        'time': datetime.now().strftime("%H:%M:%S"),
        'type': type, 'msg': msg, 'ip': ip, 'filename': filename
    })

def record_activity(ip, action=None, device_type=None):
    now = datetime.now()
    if not device_type: device_type = get_device_type(request.user_agent)
    if ip not in ACTIVE_PEERS:
        ACTIVE_PEERS[ip] = {'last_seen': now, 'action': 'idle', 'action_time': now, 'device_type': device_type}
    else:
        ACTIVE_PEERS[ip]['last_seen'] = now
        if action:
            ACTIVE_PEERS[ip]['action'] = action
            ACTIVE_PEERS[ip]['action_time'] = now + timedelta(seconds=3)
        if device_type: ACTIVE_PEERS[ip]['device_type'] = device_type

def check_peers_lifecycle():
    global LAST_ONLINE_IPS
    now = datetime.now()
    to_remove = []
    current_ips = set()
    for ip, data in ACTIVE_PEERS.items():
        if data['action'] != 'idle' and now > data['action_time']: data['action'] = 'idle'
        if now - data['last_seen'] > timedelta(seconds=PEER_TIMEOUT): to_remove.append(ip)
        else: current_ips.add(ip)
    for ip in to_remove:
        del ACTIVE_PEERS[ip]
        add_event('leave', '已离线', ip)
    new_ips = current_ips - LAST_ONLINE_IPS
    for ip in new_ips:
        if ip != '127.0.0.1': add_event('join', '加入网络', ip)
    LAST_ONLINE_IPS = current_ips

# ================= Web 路由 =================

@app.before_request
def global_intercept():
    if SERVER_STATE['locked'] and not is_local_admin():
        if request.endpoint != 'static': abort(403, description="Maintenance Mode")
    sender_ip = request.remote_addr
    if sender_ip != '127.0.0.1' and sender_ip != 'localhost':
        if request.path.startswith('/api/') or request.path.startswith('/upload') or request.path.startswith('/download'):
            record_activity(sender_ip)

@app.route('/')
def index():
    template_path = resource_path('index.html')
    if not os.path.exists(template_path):
        return f"<h2>错误：找不到资源文件</h2><p>请联系开发者或重新下载。</p>", 404
    with open(template_path, 'r', encoding='utf-8') as f: html_content = f.read()
    return render_template_string(html_content, is_admin=is_local_admin(), local_ips=get_local_ips(), port=SERVER_STATE['current_port'])

@app.route('/api/status', methods=['GET'])
def api_status():
    check_peers_lifecycle()
    sender_ip = request.remote_addr
    is_admin = is_local_admin()
    topology = []
    if SERVER_STATE['file_pool']: topology.append({'ip': 'Server', 'status': 'idle', 'type': 'server', 'device_type': 'desktop'})
    for ip, data in ACTIVE_PEERS.items():
        topology.append({'ip': ip, 'status': data['action'], 'type': 'client', 'device_type': data.get('device_type', 'desktop')})
    
    raw_events = list(EVENT_LOG)
    client_safe_events = []
    should_mask = (not is_admin) and (not SERVER_STATE['file_pool'])
    for event in raw_events:
        evt_copy = event.copy()
        if should_mask and event['ip'] != sender_ip and event.get('filename'):
            original_name = event['filename']
            masked_name = get_masked_name(original_name)
            evt_copy['msg'] = evt_copy['msg'].replace(original_name, masked_name)
            if 'filename' in evt_copy: del evt_copy['filename']
        client_safe_events.append(evt_copy)
    
    return jsonify({'locked': SERVER_STATE['locked'], 'file_pool': SERVER_STATE['file_pool'], 'ips': get_local_ips(), 'port': SERVER_STATE['current_port'], 'topology': topology, 'events': client_safe_events})

@app.route('/api/toggle_lock', methods=['POST'])
def api_toggle_lock():
    if not is_local_admin(): return jsonify({'error': '无权操作'}), 403
    SERVER_STATE['locked'] = not SERVER_STATE['locked']
    add_event('system', '服务器锁定状态已变更', 'Server')
    return jsonify({'locked': SERVER_STATE['locked']})

@app.route('/api/toggle_pool', methods=['POST'])
def api_toggle_pool():
    if not is_local_admin(): return jsonify({'error': '无权操作'}), 403
    SERVER_STATE['file_pool'] = not SERVER_STATE['file_pool']
    state_str = "启用" if SERVER_STATE['file_pool'] else "关闭"
    add_event('pool_toggle', f'文件池模式已{state_str}', 'Server')
    return jsonify({'file_pool': SERVER_STATE['file_pool']})

@app.route('/api/files/release', methods=['GET'])
def list_release_files():
    files = []
    if os.path.exists(RELEASE_DIR):
        for f in os.listdir(RELEASE_DIR):
            path = os.path.join(RELEASE_DIR, f)
            if os.path.isfile(path): files.append({'name': f, 'size': os.path.getsize(path), 'type': 'release'})
    return jsonify(files)

@app.route('/api/files/received', methods=['GET'])
def list_received_files():
    sender_ip = request.remote_addr
    is_admin = is_local_admin()
    file_pool_active = SERVER_STATE['file_pool']
    if is_admin or file_pool_active:
        structure = {}
        if file_pool_active:
            structure['Server'] = []
            if os.path.exists(RELEASE_DIR):
                for f in os.listdir(RELEASE_DIR):
                    p = os.path.join(RELEASE_DIR, f)
                    if os.path.isfile(p): structure['Server'].append({'name': f, 'size': os.path.getsize(p), 'path_key': f"__release__/{f}", 'is_server_file': True})
        if os.path.exists(RECEIVED_DIR):
            for ip_folder in os.listdir(RECEIVED_DIR):
                ip_path = os.path.join(RECEIVED_DIR, ip_folder)
                if os.path.isdir(ip_path):
                    file_list = []
                    for f in os.listdir(ip_path):
                        f_path = os.path.join(ip_path, f)
                        if os.path.isfile(f_path): file_list.append({'name': f, 'size': os.path.getsize(f_path), 'path_key': f"{ip_folder}/{f}", 'upload_time': os.path.getmtime(f_path)})
                    if file_list:
                        file_list.sort(key=lambda x: x['upload_time'], reverse=True)
                        structure[ip_folder] = file_list
        return jsonify({'role': 'pool_view' if (file_pool_active and not is_admin) else 'admin', 'data': structure, 'my_ip': sender_ip, 'pool_enabled': file_pool_active})
    else:
        my_files = []
        my_dir = os.path.join(RECEIVED_DIR, sender_ip)
        if os.path.exists(my_dir):
            for f in os.listdir(my_dir):
                f_path = os.path.join(my_dir, f)
                if os.path.isfile(f_path): my_files.append({'name': f, 'size': os.path.getsize(f_path), 'upload_time': os.path.getmtime(f_path)})
        my_files.sort(key=lambda x: x['upload_time'], reverse=True)
        return jsonify({'role': 'client', 'data': my_files, 'pool_enabled': False})

@app.route('/api/file/delete', methods=['POST'])
def delete_file():
    if not is_local_admin(): return jsonify({'error': 'Permission denied'}), 403
    data = request.json
    target_type, target_path = data.get('type'), data.get('path')
    full_path, file_name_only = None, os.path.basename(target_path) if target_path else "未知文件"
    if target_type == 'release' or (target_path and target_path.startswith('__release__/')):
        clean_name = target_path.replace('__release__/', '') if target_path else ''
        full_path = os.path.join(RELEASE_DIR, clean_name)
        file_name_only = clean_name
    elif target_type == 'received':
        full_path = os.path.join(RECEIVED_DIR, target_path)
    if full_path and os.path.exists(full_path):
        try:
            os.remove(full_path)
            if target_type == 'received':
                parent = os.path.dirname(full_path)
                if not os.listdir(parent): os.rmdir(parent)
            add_event('delete', f'删除了 {file_name_only}', 'Server', filename=file_name_only)
            return jsonify({'success': True})
        except Exception as e: return jsonify({'error': str(e)}), 500
    return jsonify({'error': 'File not found'}), 404

@app.route('/download/<path:filename>')
def download_file(filename):
    if '..' in filename or filename.startswith('/'): abort(404)
    sender_ip = request.remote_addr
    if sender_ip != '127.0.0.1': record_activity(sender_ip, 'download')
    display_name = filename.split('/')[-1]
    add_event('download', f'下载了 {display_name}', sender_ip if sender_ip != '127.0.0.1' else 'Server', filename=display_name)
    if filename.startswith('__release__/'): return send_from_directory(RELEASE_DIR, filename.replace('__release__/', ''), as_attachment=True)
    if os.path.exists(os.path.join(RELEASE_DIR, filename)): return send_from_directory(RELEASE_DIR, filename, as_attachment=True)
    if is_local_admin() or SERVER_STATE['file_pool']:
        parts = filename.split('/', 1)
        if len(parts) == 2:
            target_dir = os.path.join(RECEIVED_DIR, parts[0])
            if os.path.exists(target_dir): return send_from_directory(target_dir, parts[1], as_attachment=True)
    abort(404)

@app.route('/upload', methods=['POST'])
def upload_file():
    uploaded_files = request.files.getlist("files")
    sender_ip, is_admin = request.remote_addr, is_local_admin()
    if not is_admin: record_activity(sender_ip, 'upload')
    save_dir = RELEASE_DIR if is_admin else os.path.join(RECEIVED_DIR, sender_ip)
    if not os.path.exists(save_dir): os.makedirs(save_dir)
    saved_count, last_file = 0, ""
    for file in uploaded_files:
        if file.filename:
            filename = file.filename
            file_path = os.path.join(save_dir, filename)
            if os.path.exists(file_path): file_path = os.path.join(save_dir, datetime.now().strftime("%H%M%S_") + filename)
            file.save(file_path)
            saved_count += 1
            last_file = filename
    if saved_count > 0:
        msg = f'上传了 {saved_count} 个文件'
        recorded_filename = last_file if saved_count == 1 else None
        if saved_count == 1: msg = f'上传了 {last_file}'
        add_event('upload', msg, sender_ip if not is_admin else 'Server', filename=recorded_filename)
    return jsonify({'message': f'成功上传 {saved_count} 个文件'})

def open_browser(port):
    time.sleep(1.5)
    webbrowser.open(f'http://127.0.0.1:{port}')

if __name__ == '__main__':
    ensure_directories()
    
    # 确定端口
    final_port = find_available_port(CONFIG['port'])
    SERVER_STATE['current_port'] = final_port
    
    ips = get_local_ips()
    ip_info = f"http://{ips[0]}:{final_port}" if ips else "http://127.0.0.1:{final_port}"

    print("\n" + "="*50)
    print(f" PondCast 服务已启动")
    print(f" -----------------------------")
    print(f" [✔] 本地访问: http://127.0.0.1:{final_port}")
    if ips:
        print(f" [✔] 局域网访问: {ip_info}")
    print(f" -----------------------------")
    print(f" [i] 文件保存路径: {os.path.abspath(RECEIVED_DIR)}")
    if final_port != CONFIG['port']:
        print(f" [!] 注意: 原定端口 {CONFIG['port']} 被占用，已切换至 {final_port}")
    print("="*50 + "\n")
    
    threading.Thread(target=open_browser, args=(final_port,)).start()
    
    try:
        app.run(host='0.0.0.0', port=final_port, debug=False)
    except Exception as e:
        print(f"启动失败: {e}")
        input("按任意键退出...")