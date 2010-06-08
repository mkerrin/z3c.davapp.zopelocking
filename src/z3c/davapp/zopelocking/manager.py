##############################################################################
#
# Copyright (c) 2007 Zope Foundation and Contributors.
# All Rights Reserved.
#
# This software is subject to the provisions of the Zope Public License,
# Version 2.1 (ZPL).  A copy of the ZPL should accompany this distribution.
# THIS SOFTWARE IS PROVIDED "AS IS" AND ANY AND ALL EXPRESS OR IMPLIED
# WARRANTIES ARE DISCLAIMED, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF TITLE, MERCHANTABILITY, AGAINST INFRINGEMENT, AND FITNESS
# FOR A PARTICULAR PURPOSE.
#
##############################################################################
"""
Implementation of the z3c.dav.interfaces.IDAVLockmanager needed to adapt
the zope.locking utiltity to integrate it into z3c.dav.
"""

from BTrees.OOBTree import OOBTree
import zope.component
import zope.interface
import zope.security.management
import zope.publisher.interfaces.http
import zope.lifecycleevent.interfaces
from zope.app.container.interfaces import IReadContainer
import z3c.dav.interfaces
import z3c.dav.locking
import z3c.dav.ifvalidator

import interfaces
import indirecttokens
import properties

WEBDAV_LOCK_KEY = "z3c.dav.lockingutils.info"

class DAVLockmanager(object):
    """

      >>> from zope.interface.verify import verifyObject
      >>> from zope.locking import utility, utils
      >>> from zope.locking.adapters import TokenBroker
      >>> from zope.traversing.browser.absoluteurl import absoluteURL

      >>> file = Demo()

    Before we register a ITokenUtility utility make sure that the
    DAVLockmanager is not lockable.

      >>> adapter = DAVLockmanager(file)
      >>> adapter.islockable()
      False

    Now create and register a ITokenUtility utility.

      >>> util = utility.TokenUtility()
      >>> zope.component.getGlobalSiteManager().registerUtility(
      ...    util, zope.locking.interfaces.ITokenUtility)
      >>> zope.component.getGlobalSiteManager().registerAdapter(
      ...    TokenBroker, (zope.interface.Interface,),
      ...    zope.locking.interfaces.ITokenBroker)

      >>> import datetime
      >>> import pytz
      >>> def hackNow():
      ...     return datetime.datetime(2006, 7, 25, 23, 49, 51)
      >>> oldNow = utils.now
      >>> utils.now = hackNow

    Test the DAVLockmanager implements the descried interface.

      >>> adapter = DAVLockmanager(file)
      >>> verifyObject(z3c.dav.interfaces.IDAVLockmanager, adapter)
      True

    The adapter should also be lockable.

      >>> adapter.islockable()
      True

    Exclusive lock token
    --------------------

      >>> locktoken = adapter.lock(u'exclusive', u'write',
      ...    u'Michael', datetime.timedelta(seconds = 3600), '0')

      >>> adapter.islocked()
      True

      >>> activelock = adapter.getActivelock(locktoken)
      >>> activelock.lockscope
      [u'exclusive']
      >>> activelock.locktype
      [u'write']
      >>> activelock.depth
      '0'
      >>> activelock.timeout
      u'Second-3600'
      >>> activelock.lockroot
      '/dummy'
      >>> activelock.owner
      u'Michael'
      >>> len(activelock.locktoken)
      1
      >>> activelock.locktoken #doctest:+ELLIPSIS
      ['opaquelocktoken:...

      >>> util.get(file) == activelock.token
      True
      >>> zope.locking.interfaces.IExclusiveLock.providedBy(activelock.token)
      True

    Now refresh the timeout on the locktoken.

      >>> adapter.refreshlock(datetime.timedelta(seconds = 7200))
      >>> adapter.getActivelock(locktoken).timeout
      u'Second-7200'

    Unlock the resource.

      >>> adapter.unlock(locktoken)
      >>> util.get(file) is None
      True
      >>> adapter.islocked()
      False
      >>> adapter.getActivelock(locktoken) is None
      True

    We can't unlock the resource twice.

      >>> adapter.unlock(locktoken)
      Traceback (most recent call last):
      ...
      ConflictError: The context is not locked, so we can't unlock it.

    Shared locking
    --------------

      >>> locktoken = adapter.lock(u'shared', u'write', u'Michael',
      ...    datetime.timedelta(seconds = 3600), '0')

      >>> activelock = adapter.getActivelock(locktoken)
      >>> activelock.lockscope
      [u'shared']
      >>> len(activelock.locktoken)
      1
      >>> activelock.locktoken #doctest:+ELLIPSIS
      ['opaquelocktoken:...

      >>> sharedlocktoken = util.get(file)
      >>> sharedlocktoken == activelock.token
      True
      >>> zope.locking.interfaces.ISharedLock.providedBy(activelock.token)
      True

    Make sure that the meta-data on the lock token is correct.

      >>> len(sharedlocktoken.annotations[WEBDAV_LOCK_KEY])
      2
      >>> sharedlocktoken.annotations[WEBDAV_LOCK_KEY]['principal_ids']
      ['michael']
      >>> len(sharedlocktoken.annotations[WEBDAV_LOCK_KEY][locktoken])
      2
      >>> sharedlocktoken.annotations[WEBDAV_LOCK_KEY][locktoken]['owner']
      u'Michael'
      >>> sharedlocktoken.annotations[WEBDAV_LOCK_KEY][locktoken]['depth']
      '0'
      >>> sharedlocktoken.duration
      datetime.timedelta(0, 3600)
      >>> sharedlocktoken.principal_ids
      frozenset(['michael'])

    We can have multiple WebDAV shared locks on a resource. We implement
    this by storing the data for the second lock token in the annotations.

      >>> locktoken2 = adapter.lock(u'shared', u'write', u'Michael 2',
      ...    datetime.timedelta(seconds = 1800), '0')
      >>> len(sharedlocktoken.annotations[WEBDAV_LOCK_KEY])
      3

    We need to keep track of the principal associated with the lock token
    our selves as we can only create one shared lock token with zope.locking,
    and after removing the first shared lock the zope.locking token will
    be removed.

      >>> sharedlocktoken.annotations[WEBDAV_LOCK_KEY]['principal_ids']
      ['michael', 'michael']
      >>> sharedlocktoken.annotations[WEBDAV_LOCK_KEY][locktoken2]['owner']
      u'Michael 2'
      >>> sharedlocktoken.annotations[WEBDAV_LOCK_KEY][locktoken2]['depth']
      '0'

    Note that the timeout is shared across the two WebDAV tokens. After
    creating the second shared lock the duration changed to the last lock
    taken out. We need to do this in order to make sure that the token is
    ended at some point. What we probable want to do here is to take the
    largest remaining duration so that a lock token doesn't expire earlier
    then expected but might last slightly longer then expected for some one.

      >>> sharedlocktoken.duration
      datetime.timedelta(0, 1800)

    After unlocking the first first locktoken the information for this token
    is removed.

      >>> adapter.unlock(locktoken)
      >>> util.get(file) == sharedlocktoken
      True
      >>> len(sharedlocktoken.annotations[WEBDAV_LOCK_KEY])
      2
      >>> sharedlocktoken.annotations[WEBDAV_LOCK_KEY]['principal_ids']
      ['michael']
      >>> locktoken in sharedlocktoken.annotations[WEBDAV_LOCK_KEY]
      False
      >>> locktoken2 in sharedlocktoken.annotations[WEBDAV_LOCK_KEY]
      True

      >>> adapter.unlock(locktoken2)

      >>> util.get(file) is None
      True

    If an exclusive lock already exists on a file from an other application
    then this should fail with an already locked response.

      >>> exclusivelock = util.register(
      ...    zope.locking.tokens.ExclusiveLock(file, 'michael'))
      >>> adapter.lock(u'shared', u'write', u'Michael2',
      ...    datetime.timedelta(seconds = 3600), '0') #doctest:+ELLIPSIS
      Traceback (most recent call last):
      ...
      AlreadyLocked: <z3c.davapp.zopelocking.tests.Demo object at ...>: None
      >>> exclusivelock.end()

    If a shared lock is taken out on the resource, then this lock token is
    probable not annotated with the extra information required by WebDAV.

      >>> sharedlock = util.register(
      ...    zope.locking.tokens.SharedLock(file, ('michael',)))
      >>> len(sharedlock.annotations)
      0
      >>> locktoken = adapter.lock(u'shared', u'write', u'Michael 2',
      ...    datetime.timedelta(seconds = 3600), '0')
      >>> len(sharedlock.annotations[WEBDAV_LOCK_KEY])
      2
      >>> sharedlock.annotations[WEBDAV_LOCK_KEY]['principal_ids']
      ['michael']
      >>> locktoken in sharedlock.annotations[WEBDAV_LOCK_KEY]
      True
      >>> sharedlock.principal_ids
      frozenset(['michael'])
      >>> sharedlock.end()

    Recursive lock support
    ----------------------

      >>> demofolder = DemoFolder()
      >>> demofolder['demo'] = file

      >>> adapter = DAVLockmanager(demofolder)
      >>> locktoken = adapter.lock(u'exclusive', u'write',
      ...    u'MichaelK', datetime.timedelta(seconds = 3600), 'infinity')

      >>> demotoken = util.get(file)
      >>> interfaces.IIndirectToken.providedBy(demotoken)
      True

      >>> activelock = adapter.getActivelock(locktoken)
      >>> activelock.lockroot
      '/dummy/'
      >>> DAVLockmanager(file).getActivelock(locktoken).lockroot
      '/dummy/'
      >>> absoluteURL(file, None)
      '/dummy/dummy'
      >>> activelock.lockscope
      [u'exclusive']

    Already locked
    --------------

    Adapter is now defined on the demofolder.

      >>> adapter.lock(u'exclusive', u'write', u'Michael',
      ...    datetime.timedelta(seconds = 100), 'infinity') #doctest:+ELLIPSIS
      Traceback (most recent call last):
      ...
      AlreadyLocked...
      >>> adapter.islocked()
      True

      >>> adapter.unlock(locktoken[0])

      >>> locktoken = DAVLockmanager(file).lock(u'shared', u'write',
      ...    u'Michael', datetime.timedelta(seconds = 3600), '0')
      >>> adapter.lock(u'shared', u'write', u'Michael 2',
      ...    datetime.timedelta(seconds = 3600), 'infinity') #doctest:+ELLIPSIS
      Traceback (most recent call last):
      ...
      AlreadyLocked:...

    Some error conditions
    ---------------------

      >>> adapter.lock(u'notexclusive', u'write', u'Michael',
      ...    datetime.timedelta(seconds = 100), 'infinity') # doctest:+ELLIPSIS
      Traceback (most recent call last):
      ...
      UnprocessableError: ...

    Cleanup
    -------

      >>> zope.component.getGlobalSiteManager().unregisterUtility(
      ...    util, zope.locking.interfaces.ITokenUtility)
      True
      >>> zope.component.getGlobalSiteManager().unregisterAdapter(
      ...    TokenBroker, (zope.interface.Interface,),
      ...    zope.locking.interfaces.ITokenBroker)
      True
      >>> utils.now = oldNow

    """
    zope.interface.implements(z3c.dav.interfaces.IDAVLockmanager)
    zope.component.adapts(zope.interface.Interface)

    def __init__(self, context):
        self.context = self.__parent__ = context

    def islockable(self):
        utility = zope.component.queryUtility(
            zope.locking.interfaces.ITokenUtility,
            context = self.context, default = None)
        return utility is not None

    def maybeRecursivelyLockIndirectly(self, utility,
                                       context, roottoken, depth):
        if depth == "infinity" and IReadContainer.providedBy(context):
            for subob in context.values():
                token = utility.get(subob)
                if token:
                    raise z3c.dav.interfaces.AlreadyLocked(
                        subob, message = u"Sub-object is already locked")
                indirecttoken = indirecttokens.IndirectToken(subob, roottoken)
                utility.register(indirecttoken)
                self.maybeRecursivelyLockIndirectly(
                    utility, subob, roottoken, depth)

    def register(self, utility, token):
        try:
            return utility.register(token)
        except zope.locking.interfaces.RegistrationError:
            raise z3c.dav.interfaces.AlreadyLocked(
                token.context, message = u"Context is locked")

    def lock(self, scope, type, owner, duration, depth):
        principal_id = getPrincipalId()
        utility = zope.component.getUtility(
            zope.locking.interfaces.ITokenUtility, context = self.context)

        locktoken = z3c.dav.locking.generateLocktoken()

        if scope == u"exclusive":
            roottoken = self.register(
                utility, zope.locking.tokens.ExclusiveLock(
                    self.context, principal_id, duration = duration))
            annots = roottoken.annotations[WEBDAV_LOCK_KEY] = OOBTree()
        elif scope == u"shared":
            # A successful request for a new shared lock MUST result in the
            # generation of a unique lock associated with the requesting
            # principal. Thus if five principals have taken out shared write
            # locks on the same resource there will be five locks and five
            # lock tokens, one for each principal.
            roottoken = utility.get(self.context)
            if roottoken is None:
                roottoken = self.register(
                    utility, zope.locking.tokens.SharedLock(
                        self.context, (principal_id,), duration = duration))
                annots = roottoken.annotations[WEBDAV_LOCK_KEY] = OOBTree()
                annots["principal_ids"] = [principal_id]
            else:
                if not zope.locking.interfaces.ISharedLock.providedBy(roottoken):
                    # We need to some how figure out how to add preconditions
                    # code to the exceptions. As a 'no-conflicting-lock'
                    # precondition code is valid here. 
                    raise z3c.dav.interfaces.AlreadyLocked(
                        self.context,
                        message = u"""A conflicting lock already exists for
                                      this resource""")

                roottoken.add((principal_id,))
                roottoken.duration = duration
                if WEBDAV_LOCK_KEY not in roottoken.annotations:
                    # Locked by an alternative application
                    annots = roottoken.annotations[WEBDAV_LOCK_KEY] = OOBTree()
                    # Use OOBTree here
                    annots["principal_ids"] = [principal_id]
                else:
                    annots = roottoken.annotations[WEBDAV_LOCK_KEY]
                    annots["principal_ids"].append(principal_id)
        else:
            raise z3c.dav.interfaces.UnprocessableError(
                self.context,
                message = u"Invalid lockscope supplied to the lock manager")

        annots[locktoken] = OOBTree()
        annots[locktoken].update({"owner": owner, "depth": depth})

        self.maybeRecursivelyLockIndirectly(
            utility, self.context, roottoken, depth)

        return locktoken

    def getActivelock(self, locktoken, request = None):
        # Note that this is only used for testing purposes.
        if self.islocked():
            token = zope.locking.interfaces.ITokenBroker(self.context).get()
            return properties.DAVActiveLock(
                locktoken, token, self.context, request)
        return None

    def refreshlock(self, timeout):
        token = zope.locking.interfaces.ITokenBroker(self.context).get()
        token.duration = timeout

    def unlock(self, locktoken):
        utility = zope.component.getUtility(
            zope.locking.interfaces.ITokenUtility, context = self.context)
        token = utility.get(self.context)
        if token is None:
            raise z3c.dav.interfaces.ConflictError(
                self.context,
                message = "The context is not locked, so we can't unlock it.")

        if interfaces.IIndirectToken.providedBy(token):
            token = token.roottoken

        if zope.locking.interfaces.IExclusiveLock.providedBy(token):
            token.end()
        elif zope.locking.interfaces.ISharedLock.providedBy(token):
            principal_id = getPrincipalId()
            annots = token.annotations[WEBDAV_LOCK_KEY]
            del annots[locktoken]
            annots["principal_ids"].remove(principal_id)
            if principal_id not in annots["principal_ids"]:
                # will end token if no principals left
                token.remove((principal_id,))
        else:
            raise ValueError("Unknown lock token")

    def islocked(self):
        tokenBroker = zope.locking.interfaces.ITokenBroker(self.context)
        return tokenBroker.get() is not None


def getPrincipalId():
    principal_ids = [
        participation.principal.id
        for participation in
        zope.security.management.getInteraction().participations]

    if len(principal_ids) != 1:
        raise ValueError("There must be only one participant principal")
    principal_id = principal_ids[0]

    return principal_id

###############################################################################
#
# These event handlers enforce the WebDAV lock model. Namely on modification
# we need to check the `IF` header to see if the client knows about any
# locks on the object, and if they don't then a AlreadyLocked exception
# should be raised.
#
# We only do these checks for non-browser methods (i.e. not GET, HEAD or POST)
# as web browsers never send the `IF` header, and will always fail this test.
# For the browser methods we should use a specialized security policy like
# zc.tokenpolicy instead.
#
# Note that the events that tigger these handlers are always emitted after
# the fact, so any security assertions that might raise an exception will
# have done so before these tests, so if any condition outside the WebDAV
# lock model occurs then an AlreadyLocked exception must be raised which will
# abort the transaction and set the appropriate status and body to send to
# the client
#
###############################################################################

BROWSER_METHODS = ("GET", "HEAD", "POST")

@zope.component.adapter(zope.app.container.interfaces.IObjectMovedEvent)
def indirectlyLockObjectOnMovedEvent(event):
    """
    This event handler listens for IObjectAddedEvent, IObjectRemovedEvent as
    while as IObjectMovedEvents and is responsible for testing whether the
    container modification in question is allowed.

      >>> import UserDict
      >>> import datetime
      >>> from zope.locking import utility
      >>> from zope.publisher.browser import TestRequest
      >>> from zope.security.proxy import removeSecurityProxy
      >>> from zope.app.container.contained import ObjectAddedEvent
      >>> from zope.app.container.contained import ObjectRemovedEvent
      >>> from zope.app.container.contained import ObjectMovedEvent

      >>> class ReqAnnotation(UserDict.IterableUserDict):
      ...    zope.interface.implements(zope.annotation.interfaces.IAnnotations)
      ...    def __init__(self, request):
      ...        self.data = request._environ.setdefault('annotation', {})
      >>> zope.component.getGlobalSiteManager().registerAdapter(
      ...    ReqAnnotation, (zope.publisher.interfaces.http.IHTTPRequest,))

      >>> class Statetokens(object):
      ...    zope.interface.implements(z3c.dav.ifvalidator.IStateTokens)
      ...    def __init__(self, context, request, view):
      ...        self.context = context
      ...    schemes = ('', 'opaquetoken')
      ...    @property
      ...    def tokens(self):
      ...        context = removeSecurityProxy(self.context) # ???
      ...        if getattr(context, '_tokens', None) is not None:
      ...            return context._tokens
      ...        return []
      >>> zope.component.getGlobalSiteManager().registerAdapter(
      ...    Statetokens, (None, TestRequest, None))

    Now some content.

      >>> util = utility.TokenUtility()
      >>> zope.component.getGlobalSiteManager().registerUtility(
      ...    util, zope.locking.interfaces.ITokenUtility)

      >>> demofolder = DemoFolder()

    Nothing is locked at this stage so the test passes.

      >>> file1 = Demo()
      >>> demofolder['file1'] = file1
      >>> indirectlyLockObjectOnMovedEvent(
      ...    ObjectAddedEvent(file1, demofolder, 'file1'))
      >>> util.get(file1) is None
      True

    If a collection is locked with an infinite depth lock then all member
    resources are indirectly locked. Any resource that is added to this
    collection then becomes indirectly locked against the lockroot for
    the collection.

      >>> adapter = DAVLockmanager(demofolder)
      >>> locktoken = adapter.lock(u'exclusive', u'write',
      ...    u'MichaelK', datetime.timedelta(seconds = 3600), 'infinity')

      >>> file2 = Demo()
      >>> demofolder['file2'] = file2
      >>> indirectlyLockObjectOnMovedEvent(
      ...    ObjectAddedEvent(file2, demofolder, 'file2'))
      >>> file2lock = util.get(file2)
      >>> interfaces.IIndirectToken.providedBy(file2lock)
      True
      >>> file2lock.roottoken == util.get(demofolder)
      True

    If we rerun the event handler the new object is already locked, we
    get an AlreadyLocked exception as I don't know how to merge lock tokens,
    which might be possible under circumstances.

      >>> indirectlyLockObjectOnMovedEvent(
      ...    ObjectAddedEvent(file2, demofolder, 'file2')) #doctest:+ELLIPSIS
      Traceback (most recent call last):
      ...
      AlreadyLocked: <z3c.davapp.zopelocking.tests.Demo object at ...>: None

    An `IF` header must be present in the request object in-order for us
    to be allowed to remove this.

      >>> file2._tokens = ['statetoken']
      >>> indirectlyLockObjectOnMovedEvent(
      ...    ObjectRemovedEvent(file2, demofolder, 'file2')) #doctest:+ELLIPSIS
      Traceback (most recent call last):
      ...
      AlreadyLocked: <z3c.davapp.zopelocking.tests.Demo object at ...>: None

    Now if we set the request annotation right the event handler doesn't
    raise a AlreadyLocked request.

      >>> request = zope.security.management.getInteraction().participations[0]
      >>> ReqAnnotation(request)[z3c.dav.ifvalidator.STATE_ANNOTS] = {
      ...    '/file2': {'statetoken': True}}
      >>> indirectlyLockObjectOnMovedEvent(
      ...    ObjectRemovedEvent(file2, demofolder, 'file2'))

    `IF` access was granted to the source folder, and the destination folder
    is not locked is this is allowed.

      >>> demofolder2 = DemoFolder()
      >>> indirectlyLockObjectOnMovedEvent(
      ...    ObjectMovedEvent(file2, demofolder, 'file2',
      ...                     demofolder2, 'file3'))

    Now the state token for the demofolder2 object matches a state token
    in the `IF` header but it isn't specific for this resource or any of its
    parents.

      >>> demofolder['subfolder'] = demofolder2
      >>> adapter2 = DAVLockmanager(demofolder2)
      >>> locktoken2 = adapter2.lock(u'exclusive', u'write', u'Michael 2',
      ...    datetime.timedelta(seconds = 3600), 'infinity')
      >>> demofolder2._tokens = ['statetoken']
      >>> indirectlyLockObjectOnMovedEvent(
      ...    ObjectMovedEvent(file2, demofolder, 'file2',
      ...                     demofolder2, 'file3')) #doctest:+ELLIPSIS
      Traceback (most recent call last):
      ...
      AlreadyLocked: <z3c.davapp.zopelocking.tests.Demo object at ...>: None

    But if we update the request annotation, we still fail because the
    object we are moving is still locked.

      >>> ReqAnnotation(request)[
      ...    z3c.dav.ifvalidator.STATE_ANNOTS]['/subfolder'] = {
      ...        'statetoken': True}
      >>> indirectlyLockObjectOnMovedEvent(
      ...    ObjectMovedEvent(file2, demofolder, 'file2',
      ...                     demofolder2, 'file3')) #doctest:+ELLIPSIS
      Traceback (most recent call last):
      ...
      AlreadyLocked: <z3c.davapp.zopelocking.tests.Demo object at ...>: None

    Move to same folder, the destination folder is locked, but the object is
    not.

      >>> file3 = Demo()
      >>> demofolder['file3'] = file3
      >>> indirectlyLockObjectOnMovedEvent(
      ...    ObjectMovedEvent(file3, demofolder, 'file3',
      ...                     demofolder, 'file4'))

    Indirect tokens.

      >>> roottoken = util.get(demofolder)
      >>> zope.locking.interfaces.IExclusiveLock.providedBy(roottoken)
      True
      >>> subfolder = DemoFolder()
      >>> demofolder['subfolder'] = subfolder
      >>> indirectlyLockObjectOnMovedEvent(
      ...    ObjectAddedEvent(subfolder, demofolder, 'subfolder'))
      >>> subtoken = util.get(subfolder)
      >>> interfaces.IIndirectToken.providedBy(subtoken)
      True
      >>> subtoken.roottoken == roottoken
      True

      >>> subsubfolder = DemoFolder()
      >>> subfolder['subfolder'] = subsubfolder
      >>> indirectlyLockObjectOnMovedEvent(
      ...    ObjectAddedEvent(subsubfolder, subfolder, 'subsubfolder'))
      >>> subsubtoken = util.get(subsubfolder)
      >>> interfaces.IIndirectToken.providedBy(subsubtoken)
      True
      >>> subsubtoken.roottoken == roottoken
      True

    But this eventhandler never raises exceptions for any of the browser
    methods, GET, HEAD, POST.

      >>> del ReqAnnotation(request)[z3c.dav.ifvalidator.STATE_ANNOTS]
      >>> request.method = 'POST'
      >>> indirectlyLockObjectOnMovedEvent(
      ...    ObjectRemovedEvent(file2, demofolder, 'file2'))

    Cleanup
    -------

      >>> zope.component.getGlobalSiteManager().unregisterUtility(
      ...    util, zope.locking.interfaces.ITokenUtility)
      True
      >>> zope.component.getGlobalSiteManager().unregisterAdapter(
      ...    ReqAnnotation, (zope.publisher.interfaces.http.IHTTPRequest,))
      True
      >>> zope.component.getGlobalSiteManager().unregisterAdapter(
      ...    Statetokens, (None, TestRequest, None))
      True

    """
    utility = zope.component.queryUtility(
        zope.locking.interfaces.ITokenUtility, context = event.object)
    if not utility:
        # If there is no utility then is nothing that we can check against.
        return

    # This is an hack to get at the current request object
    interaction = zope.security.management.queryInteraction()
    if interaction:
        request = interaction.participations[0]
        if zope.publisher.interfaces.http.IHTTPRequest.providedBy(request) \
               and request.method not in BROWSER_METHODS:
            objectToken = utility.get(event.object)
            if objectToken:
                # The object is been moved out of its parent - hance we need
                # to validate that we are allowed to perform this
                # modification.
                if event.oldParent is not None and \
                       not z3c.dav.ifvalidator.matchesIfHeader(
                           event.object, request):
                    raise z3c.dav.interfaces.AlreadyLocked(
                        event.object, "Locked object cannot be moved ")
                # Otherwise since the oldParent hasn't changed we don't
                # need to check if we are allowed to perform this action,
                # this is probable a copy.
            if event.newParent is not None:
                # Probable an object added event, the object lock must be
                # consistent we the lock on its parent.
                parentToken = utility.get(event.newParent)
                if parentToken is not None:
                    if not z3c.dav.ifvalidator.matchesIfHeader(
                        event.newParent, request):
                        raise z3c.dav.interfaces.AlreadyLocked(
                            event.object, "Destination folder is locked") 
                    if objectToken is not None:
                        # XXX - this needs to be smarter. We the lock on
                        # the parent as depth '0' or the objectToken is
                        # indirectly locked against the parentToken then
                        # we shouldn't raise this exception.
                        raise z3c.dav.interfaces.AlreadyLocked(
                            event.object, "Locked object cannot be moved.")
                    if interfaces.IIndirectToken.providedBy(parentToken):
                        parentToken = parentToken.roottoken
                    utility.register(
                        indirecttokens.IndirectToken(event.object, parentToken))


@zope.component.adapter(zope.lifecycleevent.interfaces.IObjectModifiedEvent)
def checkLockedOnModify(event):
    """
    When a content object is modified we need to check that the client
    submitted an `IF` header that corresponds with the lock.

      >>> import UserDict
      >>> import datetime
      >>> from zope.locking import utility
      >>> import zope.publisher.interfaces.http
      >>> from zope.publisher.browser import TestRequest
      >>> from zope.security.proxy import removeSecurityProxy
      >>> from zope.lifecycleevent import ObjectModifiedEvent

    Some adapters needed to represent the data stored in the `IF` header,
    and the current state tokens for the content.

      >>> class ReqAnnotation(UserDict.IterableUserDict):
      ...    zope.interface.implements(zope.annotation.interfaces.IAnnotations)
      ...    def __init__(self, request):
      ...        self.data = request._environ.setdefault('annotation', {})
      >>> zope.component.getGlobalSiteManager().registerAdapter(
      ...    ReqAnnotation, (zope.publisher.interfaces.http.IHTTPRequest,))

      >>> class Statetokens(object):
      ...    zope.interface.implements(z3c.dav.ifvalidator.IStateTokens)
      ...    def __init__(self, context, request, view):
      ...        self.context = context
      ...    schemes = ('', 'opaquetoken')
      ...    @property
      ...    def tokens(self):
      ...        context = removeSecurityProxy(self.context) # ???
      ...        if getattr(context, '_tokens', None) is not None:
      ...            return context._tokens
      ...        return []
      >>> zope.component.getGlobalSiteManager().registerAdapter(
      ...    Statetokens, (None, TestRequest, None))

      >>> util = utility.TokenUtility()
      >>> zope.component.getGlobalSiteManager().registerUtility(
      ...    util, zope.locking.interfaces.ITokenUtility)

      >>> demofolder = DemoFolder()
      >>> demofile = Demo()
      >>> demofolder['demofile'] = demofile

    The test passes when the object is not locked.

      >>> checkLockedOnModify(ObjectModifiedEvent(demofile))

    Lock the file and setup the request annotation.

      >>> adapter = DAVLockmanager(demofile)
      >>> locktoken = adapter.lock(u'exclusive', u'write',
      ...    u'Michael', datetime.timedelta(seconds = 3600), '0')

      >>> request = zope.security.management.getInteraction().participations[0]
      >>> ReqAnnotation(request)[z3c.dav.ifvalidator.STATE_ANNOTS] = {
      ...    '/demofile': {'statetoken': True}}

      >>> demofile._tokens = ['wrongstatetoken'] # wrong token.
      >>> checkLockedOnModify(ObjectModifiedEvent(demofile)) #doctest:+ELLIPSIS
      Traceback (most recent call last):
      ...
      AlreadyLocked: <z3c.davapp.zopelocking.tests.Demo object at ...>: None

    With the correct lock token submitted the test passes.

      >>> demofile._tokens = ['statetoken'] # wrong token.
      >>> checkLockedOnModify(ObjectModifiedEvent(demofile))

    Child of locked token.

      >>> ReqAnnotation(request)[z3c.dav.ifvalidator.STATE_ANNOTS] = {
      ...    '/': {'statetoken': True}}
      >>> demofile._tokens = ['statetoken']
      >>> checkLockedOnModify(ObjectModifiedEvent(demofile))

    Cleanup
    -------

      >>> zope.component.getGlobalSiteManager().unregisterAdapter(
      ...    ReqAnnotation, (zope.publisher.interfaces.http.IHTTPRequest,))
      True
      >>> zope.component.getGlobalSiteManager().unregisterAdapter(
      ...    Statetokens, (None, TestRequest, None))
      True
      >>> zope.component.getGlobalSiteManager().unregisterUtility(
      ...    util, zope.locking.interfaces.ITokenUtility)
      True

    """
    # This is an hack to get at the current request object
    interaction = zope.security.management.queryInteraction()
    if interaction:
        request = interaction.participations[0]
        if zope.publisher.interfaces.http.IHTTPRequest.providedBy(request) \
               and request.method not in BROWSER_METHODS:
            if not z3c.dav.ifvalidator.matchesIfHeader(event.object, request):
                raise z3c.dav.interfaces.AlreadyLocked(
                    event.object, "Modifing locked object is not permitted.")
