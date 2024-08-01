import json
import threading
from socket import *
from time import ctime, time

class PyChattingServer:
    __socket = socket(AF_INET, SOCK_STREAM, 0)
    __address = ('', 12231)
    __buf = 1024

    def __init__(self):
        self.__socket.bind(self.__address)
        self.__socket.listen(20)
        self.__msg_handler = ChattingHandler()

    def start_session(self):
        print('已经上线，用户可通过客户端输入IP进入\r\n')
        input_thread_handler = threading.Thread(target=self.input_thread)
        input_thread_handler.daemon = True
        input_thread_handler.start()
        try:
            while True:
                cs, caddr = self.__socket.accept()
                # 利用handler来管理线程,实现线程之间的socket的相互通信
                self.__msg_handler.start_thread(cs, caddr)
        except socket.error:
            pass

    def input_thread(self):
        while True:
            command = input("")
            self.__msg_handler.add_to_blacklist_manual(command.strip())

class ChattingThread(threading.Thread):
    __buf = 32767

    def __init__(self, cs, caddr, msg_handler):
        super(ChattingThread, self).__init__()
        self.__cs = cs
        self.__caddr = caddr
        self.__msg_handler = msg_handler
        self.__last_msg_time = time()
        self.__msg_count = 0

    def run(self):
        try:
            print('连接来自于:', self.__caddr)
            if self.__msg_handler.is_blacklisted(self.__caddr[0]):
                self.__handle_blacklisted()
                return
            data = "欢迎你来到由PixelChat驱动的聊天室！请遵守以下规则：\r\n"\
                       "1. 不要刷屏，否则将会被踢出\r\n"\
                       "2. 不要骂人，可以吐槽，但要适度\r\n"\
                       "3. 如有问题请联系服务器管理员\r\n"\
                       "4. 不要发布违反国家法律的信息\r\n"\
                       "如果你同意以上内容，请输入昵称加入服务器~"
            self.__cs.sendall(bytes(data, 'utf-8'))
            while True:
                if self.__msg_handler.is_blacklisted(self.__caddr[0]):
                    self.__handle_blacklisted()
                    return
                data = self.__cs.recv(self.__buf).decode('utf-8')
                if not data:
                    break
                if len(data) > 15000:
                    self.__msg_handler.add_to_blacklist(self.__caddr[0])
                    self.__handle_blacklisted()
                    return
                current_time = time()
                if current_time - self.__last_msg_time < 12:  # 12秒内发送多条消息
                    self.__msg_count += 1
                    if self.__msg_count > 12:
                        self.__msg_handler.add_to_blacklist(self.__caddr[0])
                        self.__handle_blacklisted()
                        return
                else:
                    self.__msg_count = 0
                self.__last_msg_time = current_time
                self.__msg_handler.handle_msg(data, self.__cs)
                print(data)
        except Exception as e:
            print(f"Error in thread: {e}")
        finally:
            self.__msg_handler.close_conn(self.__cs)
            self.__cs.close()

    def __handle_blacklisted(self):
        print('...黑塔安全拦截的用户：', self.__caddr)
        data = '拒绝访问！请联系管理员处理'
        self.__cs.sendall(bytes(data, 'utf-8'))
        self.__cs.close()

class ChattingHandler:
    __help_str = "[ 系统消息 ]\r\n" \
                 "输入/checkol,即可获得所有登陆用户信息\r\n" \
                 "输入/help,即可获得帮助\r\n" \
                 "输入/exit,即可退出\r\n" \
                 "输入@用户名 (注意用户名后面的空格)+消息,即可发动单聊\r\n" \
                 "输入/i,即可屏蔽群聊信息\r\n" \
                 "再次输入/i,即可取消屏蔽\r\n" \
                 "所有首字符为/的信息都不会发送出去"

    __buf = 32767
    __socket_list = []
    __user_name_to_socket = {}
    __socket_to_user_name = {}
    __user_name_to_broadcast_state = {}
    __blacklist = set()

    def start_thread(self, cs, caddr):
        self.__socket_list.append(cs)
        chat_thread = ChattingThread(cs, caddr, self)
        chat_thread.start()

    def close_conn(self, cs):
        if cs not in self.__socket_list:
            return
        nickname = "SOMEONE"
        if cs in self.__socket_list:
            self.__socket_list.remove(cs)
        if cs in self.__socket_to_user_name:
            nickname = self.__socket_to_user_name[cs]
            self.__user_name_to_socket.pop(self.__socket_to_user_name[cs])
            self.__socket_to_user_name.pop(cs)
            self.__user_name_to_broadcast_state.pop(nickname)
            nickname += " 离开了本聊天室"
        if nickname != "SOMEONE":  # 说明是正常退出，一个防输出卡死机制，来自 boom hack 0x3299f
            self.broadcast_system_msg(nickname)

    def handle_msg(self, msg, cs):
        js = json.loads(msg)
        if js['type'] == "login":
            if js['msg'] not in self.__user_name_to_socket:
                if ' ' in js['msg']:
                    self.send_to(json.dumps({
                        'type': 'login',
                        'success': False,
                        'msg': '账号不能够带有空格'
                    }), cs)
                else:
                    self.__user_name_to_socket[js['msg']] = cs
                    self.__socket_to_user_name[cs] = js['msg']
                    self.__user_name_to_broadcast_state[js['msg']] = True
                    self.send_to(json.dumps({
                        'type': 'login',
                        'success': True,
                        'msg': '昵称建立成功,输入/checkol可查看所有在线的人,输入/help可以查看帮助(所有首字符为/的消息都不会发送)'
                    }), cs)
                    self.broadcast_系统消息_msg(js['msg'] + "加入了聊天")
            else:
                self.send_to(json.dumps({
                    'type': 'login',
                    'success': False,
                    'msg': '账号已存在'
                }), cs)
        elif js['type'] == "broadcast":
            if self.__user_name_to_broadcast_state[self.__socket_to_user_name[cs]]:
                self.broadcast(js['msg'], cs)
            else:
                self.send_to(json.dumps({
                    'type': 'broadcast',
                    'msg': '屏蔽模式下无法发送群聊信息，输入/i解除屏蔽'
                }), cs)
        elif js['type'] == "ls":
            self.send_to(json.dumps({
                'type': 'ls',
                'msg': self.get_all_login_user_info()
            }), cs)
        elif js['type'] == "help":
            self.send_to(json.dumps({
                'type': 'help',
                'msg': self.__help_str
            }), cs)
        elif js['type'] == "sendto":
            self.single_chatting(cs, js['nickname'], js['msg'])
        elif js['type'] == "ignore":
            self.exchange_ignore_state(cs)
        elif js['type'] == "exit":  # 添加处理退出消息
            self.close_conn(cs)

    def exchange_ignore_state(self, cs):
        if cs in self.__socket_to_user_name:
            state = self.__user_name_to_broadcast_state[self.__socket_to_user_name[cs]]
            state = not state
            self.__user_name_to_broadcast_state[self.__socket_to_user_name[cs]] = state
            msg = "通常模式" if state else "屏蔽模式"
            self.send_to(json.dumps({
                'type': 'ignore',
                'success': True,
                'msg': '[ %s ]\r\n[ 系统消息 ] : %s\r\n' % (ctime(), "模式切换成功,现在是" + msg)
            }), cs)
        else:
            self.send_to({
                'type': 'ignore',
                'success': False,
                'msg': '切换失败'
            }, cs)

    def single_chatting(self, cs, nickname, msg):
        if nickname in self.__user_name_to_socket:
            msg = '[ %s ]\r\n[ %s 发送给 %s ] : %s\r\n' % (
                ctime(), self.__socket_to_user_name[cs], nickname, msg)
            self.send_to_list(json.dumps({
                'type': 'single',
                'msg': msg
            }), self.__user_name_to_socket[nickname], cs)
        else:
            self.send_to(json.dumps({
                'type': 'single',
                'msg': '该用户不存在'
            }), cs)
        print(nickname)

    def send_to_list(self, msg, *cs):
        for i in range(len(cs)):
            self.send_to(msg, cs[i])

    def get_all_login_user_info(self):
        login_list = "[ 系统消息 ] 在线用户 : "
        for key in self.__socket_to_user_name:
            login_list += self.__socket_to_user_name[key] + " | "
        return login_list

    def send_to(self, msg, cs):
        if cs not in self.__socket_list:
            self.__socket_list.append(cs)
        cs.sendall(bytes(msg, 'utf-8'))

    def broadcast_系统消息_msg(self, msg):
        data = '[ %s ]\r\n[ 系统消息 ] : %s' % (ctime(), msg)
        js = json.dumps({
            'type': '系统消息_msg',
            'msg': data
        })
        for i in range(len(self.__socket_list)):
            if self.__socket_list[i] in self.__socket_to_user_name:
                self.__socket_list[i].sendall(bytes(js, 'utf-8'))

    def broadcast(self, msg, cs):
        data = '[ %s ]\r\n[%s] : %s\r\n' % (ctime(), self.__socket_to_user_name[cs], msg)
        if '' in data: # 屏蔽卡死服务器的字符，所有 Contributors 请不要更改这条判断，否则 PR 将直接拒绝合并，本安全措施来自 boom hack 0x3657f
            data = '[ %s ]\r\n[ 系统警告 - %s ] : %s\r\n' % (ctime(), self.__socket_to_user_name[cs], '{用户发送的内容可能包含卡死服务器的内容，已经被屏蔽显示}')
        js = json.dumps({
            'type': 'broadcast',
            'msg': data
        })
        for i in range(len(self.__socket_list)):
            if self.__socket_list[i] in self.__socket_to_user_name \
                    and self.__user_name_to_broadcast_state[self.__socket_to_user_name[self.__socket_list[i]]]:
                self.__socket_list[i].sendall(bytes(js, 'utf-8'))

    def is_blacklisted(self, ip):
        return ip in self.__blacklist

    def add_to_blacklist(self, ip):
        self.__blacklist.add(ip)

    def add_to_blacklist_manual(self, ip):
        if ip == '.ban':
            ip = input("请输入需要封禁的ip地址：")
            if not self.is_blacklisted(ip):
                self.__blacklist.add(ip)
                print(f"IP {ip} 已被手动加入黑名单")
            else:
                print(f"IP {ip} 已经在黑名单中")
        elif ip == '.unban':
            ip = input("请输入需要解除封禁的ip地址：")
            if not self.is_blacklisted(ip):
                print(f"IP {ip} 未在黑名单中")
            else:
                self.__blacklist.remove(ip)
                print(f"IP {ip} 已经被手动移除")
        elif ip == '.banlist':
            print(self.__blacklist)
        elif ip == '.help':
            print("BAN: 封禁某个IP\r\n"\
                  "UNBAN: 解除封禁某个IP\r\n"\
                  "BANLIST: 查看封禁IP列表\r\n"\
                  "HELP: 查看操作帮助")
        elif ip == '.an':
            user = input("请输入要发布的内容：")
            self.broadcast_system_msg(user)
            print("发布成功")
        elif ip == '.online':
            login_list = "[ 输出 ] 在线用户 : "
            for key in self.__socket_to_user_name:
                login_list += self.__socket_to_user_name[key] + ' | '
            print(login_list)
        elif ip == '.setvisit':  # 一个防输出卡死的屏蔽功能，目前仅支持手动添加，来自 boom hack 0x3299f
            ip = input("请输入限制访问信息的ip地址：")
            if not self.is_alisted(ip):
                self.__alist.add(ip)
                print(f"IP {ip} 已经被手动更改访问")
            else:
                self.__alist.remove(ip)
                print(f"IP {ip} 已经被手动更改访问")
        elif ip == '.help':
            print("BAN: 封禁某个IP\r\n"\
                  "UNBAN: 解除封禁某个IP\r\n"\
                  "BANLIST: 查看封禁IP列表\r\n"\
                  "KICK: 踢出某个用户\r\n"\
                  "AN: 以系统身份发布消息\r\n"\
                  "ONELINE: 查看在线用户\r\n"\
                  "SETVISIT: 对用户访问进行操作\r\n"\
                  "HELP: 查看操作帮助")
        else:
            print("不存在的命令！")


def main():
    server = PyChattingServer()
    server.start_session()

if __name__ == "__main__":
    main()
