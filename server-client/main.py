import json
import threading
from socket import *
from time import ctime

class PyChattingServer:
    __socket = socket(AF_INET, SOCK_STREAM, 0)
    __address = ('', 12231)
    __buf = 1024

    def __init__(self):
        self.__socket.bind(self.__address)
        self.__socket.listen(20)
        self.__msg_handler = ChattingHandler()

    def start_session(self):
        print('即时聊天系统部署完成，用户可通过客户端并输入本机IP访问！\r\n')
        try:
            while True:
                cs, caddr = self.__socket.accept()
                # 利用handler来管理线程,实现线程之间的socket的相互通信
                self.__msg_handler.start_thread(cs, caddr)
        except socket.error:
            pass

class ChattingThread(threading.Thread):
    __buf = 1024

    def __init__(self, cs, caddr, msg_handler):
        super(ChattingThread, self).__init__()
        self.__cs = cs
        self.__caddr = caddr
        self.__msg_handler = msg_handler

    def run(self):
        try:
            print('> 连接来自于:', self.__caddr)
            data = "欢迎你到来由Pixel Chat驱动的聊天室，开始聊天前请你阅读以下须知\r\n"\
                   "1. 请勿发表辱骂他人的言论\r\n"\
                   "2. 请勿发表违反国家法律的言论\r\n"\
                   "3. 请勿刷屏\r\n"\
                   "4. 本聊天工具没有换行，一行写完回车即发送\r\n"\
                   "如果您同意以上协议，请输入你的的昵称（不能带空格）并开始聊天："
            self.__cs.sendall(bytes(data, 'utf-8'))
            while True:
                data = self.__cs.recv(self.__buf).decode('utf-8')
                if not data:
                    break
                self.__msg_handler.handle_msg(data, self.__cs)
                print(data)
        except:
            pass
        finally:
            self.__msg_handler.close_conn(self.__cs)
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

    __buf = 1024
    __socket_list = []
    __user_name_to_socket = {}
    __socket_to_user_name = {}
    __user_name_to_broadcast_state = {}

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
        nickname += " "
        self.broadcast_system_msg(nickname + "离开了本聊天室，他的用户名 " + nickname + "现在开放注册")

    def handle_msg(self, msg, cs):
        js = json.loads(msg)
        if js['type'] == "login":
            if js['msg'] not in self.__user_name_to_socket:
                if ' ' in js['msg']:
                    self.send_to(json.dumps({
                        'type': 'login',
                        'success': False,
                        'msg': '账号禁止包含空格！'
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
                    self.broadcast_system_msg(js['msg'] + "加入了聊天")
            else:
                self.send_to(json.dumps({
                    'type': 'login',
                    'success': False,
                    'msg': '账号已存在，请换一个重试'
                }), cs)
        elif js['type'] == "broadcast":
            if self.__user_name_to_broadcast_state[self.__socket_to_user_name[cs]]:
                self.broadcast(js['msg'], cs)
            else:
                self.send_to(json.dumps({
                    'type': 'broadcast',
                    'msg': '屏蔽模式下无法发送群聊信息，输入/i可取消屏蔽'
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
            if state:
                state = False
            else:
                state = True
            self.__user_name_to_broadcast_state.pop(self.__socket_to_user_name[cs])
            self.__user_name_to_broadcast_state[self.__socket_to_user_name[cs]] = state
            if self.__user_name_to_broadcast_state[self.__socket_to_user_name[cs]]:
                msg = "通常模式"
            else:
                msg = "屏蔽模式"
            self.send_to(json.dumps({
                'type': 'ignore',
                'success': True,
                'msg': '[%s]\r\n[ 系统消息 ] : %s\r\n' % (ctime(), "模式切换成功,现在是" + msg)
            }), cs)
        else:
            self.send_to({
                'type': 'ignore',
                'success': False,
                'msg': '切换失败'
            }, cs)

    def single_chatting(self, cs, nickname, msg):
        if nickname in self.__user_name_to_socket:
            msg = '[%s]\r\n[ %s 发送给 %s ] : %s\r\n' % (
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
        login_list = "[ 系统消息 ] 当前在线 : "
        for key in self.__socket_to_user_name:
            login_list += self.__socket_to_user_name[key] + ","
        return login_list

    def send_to(self, msg, cs):
        if cs not in self.__socket_list:
            self.__socket_list.append(cs)
        cs.sendall(bytes(msg, 'utf-8'))

    def broadcast_system_msg(self, msg):
        data = '[%s]\r\n[ 系统消息 ] : %s' % (ctime(), msg)
        js = json.dumps({
            'type': 'system_msg',
            'msg': data
        })
        for i in range(len(self.__socket_list)):
            if self.__socket_list[i] in self.__socket_to_user_name:
                self.__socket_list[i].sendall(bytes(js, 'utf-8'))

    def broadcast(self, msg, cs):
        data = '[%s]\r\n[%s] : %s\r\n' % (ctime(), self.__socket_to_user_name[cs], msg)
        js = json.dumps({
            'type': 'broadcast',
            'msg': data
        })
        for i in range(len(self.__socket_list)):
            if self.__socket_list[i] in self.__socket_to_user_name \
                    and self.__user_name_to_broadcast_state[self.__socket_to_user_name[self.__socket_list[i]]]:
                self.__socket_list[i].sendall(bytes(js, 'utf-8'))


def main():
    server = PyChattingServer()
    server.start_session()

if __name__ == "__main__" :
    main()
