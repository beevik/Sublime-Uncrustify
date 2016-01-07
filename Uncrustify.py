import sublime, sublime_plugin
import os.path, subprocess, traceback
import re		# need regular expression operations
import fnmatch	# need Unix filename pattern matching
from merge import merge

uncrustify_settings = sublime.load_settings('Uncrustify.sublime-settings')

class EventListener(sublime_plugin.EventListener):
	def on_pre_save(self, view):
		if uncrustify_settings.get("uncrustify_on_save") and getLanguage(view):
			view.run_command('uncrustify_document')

def which(program):
    import os
    def is_exe(fpath):
        return os.path.isfile(fpath) and os.access(fpath, os.X_OK)
    fpath, fname = os.path.split(program)
    if fpath:
        if is_exe(program):
            return program
    else:
        for path in os.environ["PATH"].split(os.pathsep):
            path = path.strip('"')
            exe_file = os.path.join(path, program)
            if is_exe(exe_file):
                return exe_file
    return None

def getExecutable():
	f = uncrustify_settings.get("uncrustify_executable")
	if f:
		if not which(f):
			err = "Cannot find '%s'\n\nCheck your Uncrustify settings!" % f
			sublime.error_message(err)
			return ""
	return f

def getConfig():
	# get default config setting
	config = uncrustify_settings.get("uncrustify_config")
	if config:
		# only if exists
		if not os.path.exists(config):
			err = "Cannot find '%s'\n\nCheck your Uncrustify settings!" % config
			sublime.error_message(err)
			return ""
	else:
		# try from environment variable
		config = os.getenv("UNCRUSTIFY_CONFIG", "")
		if not config:
			err = "Need to specify the config file in Uncrustify settings\nor set UNCRUSTIFY_CONFIG in OS!"
			sublime.error_message(err)
			return ""
		# only if exists
		if not os.path.exists(config):
			err = "Cannot find '%s'\nfrom environment variable UNCRUSTIFY_CONFIG\n\nCheck your Uncrustify settings!" % config
			sublime.error_message(err)
			return ""

	return config

def getConfigByLang(lang):
	# get config setting
	configs = uncrustify_settings.get("uncrustify_config_by_lang", [])

	if len(configs) == 0:
		return "none"

	# find one matched the language
	for each in configs:
		for key, config in each.items():
			if not key or not config:
				continue

			if lang == key:
				# only if exists
				if not os.path.exists(config):
					err = "Cannot find '%s'\nfor language: %s\n\nCheck your Uncrustify settings!" % (config, lang)
					sublime.error_message(err)
					return ""
				return config

	# just no one matched
	return "none"

def getConfigByFilter(path_name):
	# get filtering rule
	rule = uncrustify_settings.get("uncrustify_filtering_rule", 0)

	# get config setting
	configs = uncrustify_settings.get("uncrustify_config_by_filter", [])

	if len(configs) == 0:
		return "none"

	if not isinstance(rule, int):
		err = "Invalid filtering rule, not an integer\n\nCheck your Uncrustify settings!"
		sublime.error_message(err)
		return ""

	if rule < 0 or rule > 2:
		err = "Invalid filtering rule: %d, out of range\n\nCheck your Uncrustify settings!" % rule
		sublime.error_message(err)
		return ""

	# force to unix style
	path_name = path_name.replace('\\', '/')

	# find one appeared in path_name
	for each in configs:
		for pattern, config in each.items():
			if not pattern or not config:
				continue

			if (rule == 0 and path_name.find(pattern) >= 0) or \
			   (rule == 1 and fnmatch.fnmatch(path_name, pattern)) or \
			   (rule == 2 and re.match(pattern, path_name)):
				# only if exists
				if not os.path.exists(config):
					err = "Cannot find '%s'\nfor pattern: %s\n\nCheck your Uncrustify settings!" % (config, pattern)
					sublime.error_message(err)
					return ""
				return config

	# just no one matched
	return "none"

def guessLanguage(ext_name):
	if ext_name == ".c":
		return "C"
	elif ext_name == ".cpp" or \
		 ext_name == ".h" or \
		 ext_name == ".cxx" or \
		 ext_name == ".hpp" or \
		 ext_name == ".hxx" or \
		 ext_name == ".cc" or \
		 ext_name == ".cp" or \
		 ext_name == ".C" or \
		 ext_name == ".CPP" or \
		 ext_name == ".c++":
		return "CPP"
	elif ext_name == ".d" or \
		 ext_name == ".di":
		return "D"
	elif ext_name == ".cs":
		return "CS"
	elif ext_name == '.java':
		return "JAVA"
	elif ext_name == ".pawn" or \
		 ext_name == ".p" or \
		 ext_name == ".sma" or \
		 ext_name == ".inl":
		return "PAWN"
	elif ext_name == ".m":
		return "OC"
	elif ext_name == ".mm":
		return "OC+"
	elif ext_name == ".vala":
		return "VALA"
	elif ext_name == ".sqc":	# embedded SQL
		return "SQL"
	elif ext_name == ".es":
		return "ECMA"
	return ""

def getLanguage(view):
	# get topmost scope
	scope = view.scope_name(view.sel()[0].end())

 	# should be source.<lang_name>
	result = re.search("\\bsource\\.([a-z+\-]+)", scope)

	lang_name = result.group(1) if result else "Plain Text"

	if lang_name == "Plain Text":
		# check if match our extension names
		path = view.file_name()
		if not path:
			msg = "Unknown language: %s" % lang_name
			return ""

		file_name, ext_name = os.path.splitext(path)
		return guessLanguage(ext_name)

	if lang_name == "c":
		return "C"
	elif lang_name == "c++":
		return "CPP"
	elif lang_name == "d":
		return "D"
	elif lang_name == "cs":
		return "CS"
	elif lang_name == 'java':
		return "JAVA"
	elif lang_name == "pawn":	# not listed in sublime default
		return "PAWN"
	elif lang_name == "objc":
		return "OC"
	elif lang_name == "objc++":
		return "OC+"
	elif lang_name == "vala":	# not listed in sublime default
		return "VALA"
	elif lang_name == "sql":
		return "C"
	elif lang_name == "es":		# not listed in sublime default
		return "ECMA"
	return ""

def reformat(view, edit):
	vsize = view.size()
	region = sublime.Region(0, vsize)
	if region.empty():
		sublime.status_message("Empty document!")
		return

	# assign the external program
	program = getExecutable()
	if not program:
		return

	command = []
	command.append(program)

	# specify the language override (because input is from stdin)
	lang = getLanguage(view)
	if not lang:
		return

	command.append("-l")
	command.append(lang)

	# specify the config file:
	# try 1
	config = getConfigByFilter(view.file_name())
	if not config:
		return
	# try 2
	if config == "none":
		config = getConfigByLang(lang)
		if not config:
			return
	# try 3
	if config == "none":
		config = getConfig()
		if not config:
			return

	command.append("-c")
	command.append(config)

	# dump command[]
	msg = ""
	for str in command:
		msg += str
		msg += " "
	print("> " + msg + "...")
	sublime.status_message(msg + "...")

	try:
		# run
		proc = subprocess.Popen(command, \
			   stdin = subprocess.PIPE, stdout = subprocess.PIPE, stderr = subprocess.PIPE)

		content = view.substr(region).encode("utf-8")
		output = proc.communicate(input=content)[0]

		# wait return
		return_code = proc.poll()
		if return_code != 0:
			stderr = proc.communicate()[1]
			if stderr:
				err = "Found error in executing '%s':\n\n%s" % (command[0], stderr.decode("utf-8"))
			else:
				err = "Found error in executing '%s':\n\nCode: %d" % (command[0], return_code)
			sublime.error_message(err)
			return

		_, err = merge(view, vsize, output.decode("utf-8"), edit)

	except (OSError, ValueError, subprocess.CalledProcessError, Exception) as e:
		if command[0] == DEFAULT_EXECUTABLE:
			err = "Cannot execute '%s' (from PATH)\n\n%s\n\nNeed to specify the executable file in Uncrustify settings!" % (command[0], e)
		else:
			err = "Cannot execute '%s'\n\n%s" % (command[0], e)
		sublime.error_message(err)

def open_file(window, file_name):
	window.open_file(file_name)

# Uncrustify the document
class UncrustifyDocumentCommand(sublime_plugin.TextCommand):
	def run(self, edit):
		reformat(self.view, edit)

# open the config file to edit
class UncrustifyOpenCfgCommand(sublime_plugin.WindowCommand):
	def run(self):
		config = getConfig()
		if not config:
			return

		# go
		open_file(self.window, config)

# open the config file which matches current document to edit
class UncrustifyOpenCfgCurrentCommand(sublime_plugin.TextCommand):
	def run(self, edit):
		# get the language
		lang = getLanguage(self.view)
		if not lang:
			return

		# specify the config file:
		# try 1, if matches one of filters
		config = getConfigByFilter(self.view.file_name())
		if not config:
			return
		# try 2, if matches one of languages
		if config == "none":
			config = getConfigByLang(lang)
			if not config:
				return
		# try 3, use default
		if config == "none":
			config = getConfig()
			if not config:
				return

		# go
		open_file(sublime.active_window(), config)
