import sublime
import sublime_plugin
import os.path
import subprocess
import re
import fnmatch

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
	exe_file = uncrustify_settings.get("uncrustify_executable")
	if exe_file:
		if not which(exe_file):
			err = "Cannot find '%s'\n\nCheck your Uncrustify settings!" % exe_file
			sublime.error_message(err)
			return ""
	return exe_file

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
	lang_dict = {
		".c": "C",
		".cpp": "CPP",
		".h": "CPP",
		".cxx": "CPP",
		".hxx": "CPP",
		".d": "D",
		".di": "D",
		".cs": "CS",
		".java": "JAVA",
		".pawn": "PAWN",
		".p": "PAWN",
		".sma": "PAWN",
		".m": "OC",
		".mm": "OC+",
		".vala": "VALA",
		".sqc": "SQL",
		".es": "ECMA"
	}
	return lang_dict.get(ext_name, "")

def getLanguage(view):
	scope = view.scope_name(view.sel()[0].end())

 	# should be source.<lang_name>
	result = re.search("\\bsource\\.([a-z0-9+\-]+)", scope)
	lang_name = result.group(1) if result else "Plain Text"

	if lang_name == "Plain Text":
		path = view.file_name()
		if not path:
			return ""
		file_name, ext_name = os.path.splitext(path)
		return guessLanguage(ext_name)

	lang_dict = {
		'c': 'C',
		'c89': 'C',
		'c99': 'C',
		'c++': 'CPP',
		'd': 'D',
		'cs': 'CS',
		'java': 'JAVA',
		'pawn': 'PAWN',
		'objc': 'OC',
		'objc++': 'OC+',
		'vala': 'VALA',
		'es': 'ECMA'
	}
	return lang_dict.get(lang_name, "")

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

	# specify the language override (because input is from stdin)
	lang = getLanguage(view)
	if not lang:
		return

	# specify the config file:
	config = getConfigByFilter(view.file_name())
	if not config:
		return
	if config == "none":
		config = getConfigByLang(lang)
		if not config:
			return
	if config == "none":
		config = getConfig()
		if not config:
			return

	command = [program, "-l", lang, "-c", config]

	# dump command to console
	msg = ' '.join(command)
	print("> " + msg)
	sublime.status_message(msg)

	try:
		proc = subprocess.Popen(command,
			   stdin = subprocess.PIPE, stdout = subprocess.PIPE,
			   stderr = subprocess.PIPE)

		content = view.substr(region).encode("utf-8")
		out, err = proc.communicate(input=content)

		return_code = proc.poll()
		if return_code != 0:
			sublime.error_message("Uncrustify error #%d:\n%s" % (return_code, err.decode("utf-8")))
			return

		dirty, err = merge(view, vsize, out.decode("utf-8"), edit)
		if err:
			sublime.error_message("Uncrustify merge error:\n%s" % (err))

	except (OSError, ValueError, subprocess.CalledProcessError, Exception) as e:
		sublime.error_message("Cannot execute '%s'\n\n%s" % (command[0], e))

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
