import os
import loclogger

from loclogger import DEBUG, trace

time = None

class MemoryCacheNotValid(Exception):
    pass

class MemoryCache(object):

    class TreeNode(object):

        class Impl(object):

            def __init__(self, parent=None):
                self.parent = parent
                self.timestamp = time.time()
                self.stat = None
                self.optionals = {}

            @staticmethod
            def listOfOptionals():
                return ['children', 'target', 'lock', 'has_all_children']

        def __init__(self, parent=None):
            self._impl = MemoryCache.TreeNode.Impl(parent)

        def __getattribute__(self, item):

            if item == '_impl':
                return object.__getattribute__(self, item)

            if hasattr(self._impl, item):
                return getattr(self._impl, item)

            if item in self._impl.optionals:
                return self._impl.optionals[item]

            if item in MemoryCache.TreeNode.Impl.listOfOptionals():
                self.optionals[item] = None
                return self.optionals[item]

            return object.__getattribute__(self, item)

        def __setattr__(self, item, value):

            if item == '_impl':
                object.__setattr__(self, item, value)

            if hasattr(self._impl, item):
                setattr(self._impl, item, value)

            if item in MemoryCache.TreeNode.Impl.listOfOptionals():
                self.optionals[item] = value

            return object.__setattr__(self, item, value)

        def __repr__(self):
            return "<TreeNode>"

    def __init__(self, cache_lifetime):
        self._root = MemoryCache.TreeNode()
        self._cache_lifetime = cache_lifetime
        self._locked = False

    @trace
    def getAttributes(self, path):
        return self._getAttributes(path)

    @trace
    def isExisting(self, path):

        attr = self._getAttributes(path)

        if attr is None:
            return None

        if attr.stat is None:
            return False

        return True

    @trace
    def listDirectory(self, path):
        node = self._get_node(path)

        if not node.has_all_children:
            raise MemoryCacheNotValid()

        return list(sorted(node.children.keys()))

    @trace
    def cacheAttributes(self, path, st = None):
        node = self._create_node(path)
        node.stat = st

    @trace
    def cacheLinkTarget(self, path, target):
        node = self._get_node(path)
        if not node:
            node = self._create_node(path)
        node.target = target

    @trace
    def readLink(self, path):
        node = self._get_node(path)
        return node

    @trace
    def hasAllChildrenAttributesCached(self, path, flag):
        node = self._get_node(path)
        if node is None:
            node = self._create_node(path)
        node.has_all_children = flag

    def _split_path(self, path):
        parts = list(filter(lambda x: not x is '', path.split(os.path.sep))) # /a//b///c became ['a', 'b', 'c']
        return parts

    def _getAttributes(self, path):
        node = self._get_node(path)
        if node:
            if node.parent is None: # i.e. root
                if node.stat is None:
                    return None

            if time.time() - node.timestamp < self._cache_lifetime:
                if loclogger.debug:
                    DEBUG("time now: " + str(time.time()) 
                          + ", memory cache lifetime: " + str(self._cache_lifetime)
                          + ", node timestamp is: " + str(node.timestamp))
                return node
            else:
                self._remove_subtree(node)
                return None
        else:
            if loclogger.debug:
                DEBUG("NO CACHE ENTRY FOR %s" % path)
            return None

    @trace
    def _get_node(self, path):
        parts = self._split_path(path)
        curr_node = self._root
        for part in parts:
            if not curr_node.children or (not part in curr_node.children):
                return None
            else:
                curr_node = curr_node.children[part]
        return curr_node

    def _create_node(self, path):
        parts = self._split_path(path)
        curr_node = self._root
        for part in parts:
            if curr_node.children is None:
                curr_node.children = {}
            if not part in curr_node.children:
                curr_node.children[part] = MemoryCache.TreeNode(curr_node)
            curr_node = curr_node.children[part]
        if curr_node is self._root:
            curr_node.timestamp = time.time()
        return curr_node

    def _remove_subtree(self, node):
        # NOTE: root is currently not removeable
        #       method is not thread safe
        if node.parent:
            # search for key with given value
            basename = [key for key, value in node.parent.children.iteritems() if value == node][0]
            DEBUG("key to remove: " + key)
            del node.parent.children[basename]
        else:
            node.stat = None # FIXME: ugly workaround - deinitialization of root



