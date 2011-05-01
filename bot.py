import irc
import pkgutil,re,traceback

class Wrapper(object):
	def __init__(self, origobj):
		self.obj = origobj
	def __str__(self):
		return "Wrapped: " + str(self.obj)
	def __getattr__(self, attr):
		return getattr(self.obj, attr)

class ConfigException(BaseException):
	pass

class Module(object):
	rule = None
	def __init__(self, bot, conf):
		self.config = conf
	def run(self, bot, params):
		pass
	def unload(self):
		pass

class Bot(irc.IRC):
	def __init__(self, config):
		irc.IRC.__init__(
				self,
				config.nick,
				config.ident,
				config.name,
				config.host,
				config.port,
				config.ssl,
				config.password,
				config.encoding
				)
		self.config = config
		self.modules = dict() # { "type" : ("pack_name", "regexp", "module") }
		self.modules["privmsg"] = list()
		self.modules["cmd"] = list()
		self.modules["kick"] = list()
		self.load_modules()
	
	def load_modules(self):
		for (importer, name, ispkg) in pkgutil.iter_modules(self.config.modules_paths):
			if name in self.config.load_modules and name not in self.config.block_modules:
				try:
					self.load_module_with_importer(importer, name)
				except BaseException as e:
					self.verbose_msg("Cannot load %s:\n%s" % (name, e))
	
	def load_module_with_importer(self, importer, pack_name, load_modules=None):
		self.verbose_msg("Loading modules from %s" % pack_name)
		loader = importer.find_module(pack_name)
		module_pack = loader.load_module(pack_name)
		module_names = module_pack.__module_class_names__
		self.verbose_msg('%s' % ', '.join(module_names))
		for module_name in module_names:
			if load_modules is None or module_name in load_modules:
				module = getattr(module_pack, module_name)
				try:
					self.verbose_msg('    %s' % module)
					obj = module(self, self.prepare_module_config(getattr(module_pack, '__module_config__', {})))
					if obj:
						m = (pack_name, re.compile(obj.rule), obj)
						if not hasattr(obj,"handler_type"):
							obj.handler_type = "privmsg"
						if self.modules[obj.handler_type] is None:
							self.modules[obj.handler_type] = list()
						self.modules[obj.handler_type].insert(0,m)
				except BaseException as e:
					self.verbose_msg('Cannot load %s from %s:\n%s\n' % (module_name, pack_name, e))
					traceback.print_exc()

	def load_module(self, pack_name, load_modules=None):
		modules = filter(lambda m: m[1] == pack_name,
				pkgutil.iter_modules(self.config.modules_paths))
		for (importer, name, ispkg) in modules:
			try:
				self.load_module_with_importer(importer, name, load_modules=load_modules)
			except BaseException as e:
				self.verbose_msg('Cannot load %s:\n%s' % (name, e))
				traceback.print_exc()
	
	def unload_module(self, pack_name, module_name=None):
		modules = list()
		for k in self.modules:
			modules.extend(filter(lambda m: m[0] == pack_name and (module_name == None or m[2].__class__.__name__ == module_name),self.modules[k]))
		for m in modules:
			self.verbose_msg('Unloading %s.%s' % (m[0], m[2]))
			self.modules[m[2].handler_type].remove(m)
			m[2].unload()
	
	def prepare_module_config(self, config):
		prepared = {}
		for key in config:
			if not isinstance(config[key][0], config[key][1]):
				raise ConfigException('config option %s needs %s, but %s given' %
						(key, config[key][1], config[key][0]))
			else:
				prepared[key] = config[key][0]
		return prepared
	
	def handle_cmd(self, sender, cmd, params):
		for m in self.modules["cmd"]:
			match = m[1].match("%s :%s" % (cmd, params))
			if match is None:
				continue
			self.verbose_msg("\t%s: match!" % m[2].__class__)
			try:
				obj = Wrapper(self)
				obj.sender = sender
				obj.cmd = cmd
				obj.params = params
				obj.match = match
				m[2].run(obj,(cmd,params))
			except BaseException as e:
				self.verbose_msg("error ! something went wrong")
				traceback.print_exc()

	def handle_privmsg(self, sender, target, msg):
		dont_do = list()
		for m in self.modules["privmsg"]:
			if m in dont_do:
				return
			dont_do.append(m)
			match = m[1].match(msg)
			if match is None:
				continue
			self.verbose_msg("\t%s: match!" % m[2].__class__)
			try:
				obj = Wrapper(self)
				obj.sender = sender
				obj.target = target
				obj.line = msg
				obj.match = match
				m[2].run(obj,(sender,msg))
			except BaseException as e:
				self.verbose_msg("error ! something went wrong")
				traceback.print_exc()

	def handle_kick(self, params):
		for m in self.modules["kick"]:
			match = m[1].match(msg)
			if match is None:
				continue
			self.verbose_msg("\t%s: match!" % m[2].__class__)
			try:
				obj = Wrapper(self)
				obj.params = params
				obj.match = match
				m[2].run(obj,(sender,msg))
			except BaseException as e:
				self.verbose_msg("error ! something went wrong")
				traceback.print_exc()
