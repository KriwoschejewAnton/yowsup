import threading, inspect, shlex
try:
    import Queue
except ImportError:
    import queue as Queue
try:
    import readline
except ImportError:
    import pyreadline as readline

class clicmd(object):
    def __init__(self, desc, order = 0):
        self.desc = desc
        self.order = order
    def __call__(self, fn):
        fn.clidesc = self.desc
        fn.cliorder = self.order
        return fn

class Cli(object):
    def __init__(self):
        self.sentCache = {}
        self.commands = {}
        self.acceptingInput = False
        self.lastPrompt = True
        self.blockingQueue = Queue.Queue()

        self._queuedCmds = []

        readline.set_completer(self.complete)
        readline.parse_and_bind('tab: complete')

        members = inspect.getmembers(self, predicate = inspect.ismethod)
        for m in members:
            if hasattr(m[1], "clidesc"):
                fname = m[0]
                fn = m[1]
                try:
                    cmd, subcommand = fname.split('_')
                except ValueError:
                    cmd = fname
                    subcommand = "_"


                if not cmd in self.commands:
                    self.commands[cmd] = {}

                self.commands[cmd][subcommand] = {
                   "args": inspect.getargspec(fn)[0][1:],
                   "optional": len(inspect.getargspec(fn)[3]) if inspect.getargspec(fn)[3] else 0,
                   "desc": fn.clidesc,
                   "fn": fn,
                   "order": fn.cliorder
                }
        #self.cv = threading.Condition()
        self.inputThread = threading.Thread(target = self.startInputThread)
        self.inputThread.daemon = True

    

    def queueCmd(self, cmd):
        self._queuedCmds.append(cmd)

    def startInput(self):
        self.inputThread.start()

    ################### cmd input parsing ####################
    def print_usage(self):
	pass

    def execCmd(self, cmdInput):
        cmdInput = cmdInput.rstrip()

        if not len(cmdInput) > 1:
            return

        if cmdInput.startswith("/"):
            cmdInput = cmdInput[1:]
        else:
            self.print_usage()
            return

        cmdInputDissect = [c for c in shlex.split(cmdInput) if c]

        cmd = cmdInputDissect[0]

        if not cmd in self.commands:
            return self.print_usage()

        cmdData = self.commands[cmd]
        if len(cmdData) == 1 and "_" in cmdData:
            subcmdData = cmdData["_"]
            args = cmdInputDissect[1:] if len(cmdInputDissect) > 1 else []
        else:
            args = cmdInputDissect[2:] if len(cmdInputDissect) > 2 else []
            subcmd = cmdInputDissect[1] if len(cmdInputDissect) > 1 else ""
            if subcmd not in cmdData:
                return self.print_usage()

            subcmdData = cmdData[subcmd]

        targetFn = subcmdData["fn"]
        if len(subcmdData["args"]) < len(args) or len(subcmdData["args"]) - subcmdData["optional"] > len(args):
            return self.print_usage()

        return self.doExecCmd(lambda :targetFn(*args))

    def doExecCmd(self, fn):
        return fn()


    def startInputThread(self):
        #cv.acquire()
        # Fix Python 2.x.
        global input
        try: input = raw_input
        except NameError: pass

        while(True):

            cmd = self._queuedCmds.pop(0) if len(self._queuedCmds) else input(self.getPrompt()).strip()
            wait = self.execCmd(cmd)
            if wait:
                self.acceptingInput = False
                self.blockingQueue.get(True)
                #cv.wait()
                #self.inputThread.wait()
            self.acceptingInput = True
        #cv.release()

    def getPrompt(self):
        return "[%s]:" % ("connected" if self.connected else "offline")

    def printPrompt(self):
        #return "Enter Message or command: (/%s)" % ", /".join(self.commandMappings)
        #p rint(self.getPrompt())
	pass

    def output(self, message, tag = "general", prompt = True):
        if self.acceptingInput == True and self.lastPrompt is True:
	    pass	
            #p rint("")


        self.lastPrompt = prompt

        if tag is not None:
            #p rint("%s: %s" % (tag, message))
	    pass
        else:
            #p rint(message)
	    pass
        if prompt:
            self.printPrompt()

    def complete(self, text, state):
        if state == 0:
            for cmd in self.commands:
                if cmd.startswith(text) and cmd != text:
                        return cmd

    def notifyInputThread(self):
        self.blockingQueue.put(1)

if __name__ == "__main__":
    c = Cli()
    c.print_usage()
