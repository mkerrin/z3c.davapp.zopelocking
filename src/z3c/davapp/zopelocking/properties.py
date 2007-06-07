##############################################################################
#
# Copyright (c) 2006 Zope Corporation and Contributors.
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
"""Support for using zope.locking has a locking mechanism for WebDAV locking.

Note that we can't use zope.locking.utility.TokenUtility has a global utility.
This is because if a recursive lock request fails half through then the
utility has already been modified and since it is not persistent
transaction.abort doesn't unlock the pervious successful locks. Since the
utility gets into an inconsistent state.

$Id: lockingutils.py 75023 2007-05-02 18:42:54Z mkerrin $
"""
__docformat__ = 'restructuredtext'

from zope import component
from zope import interface
import zope.locking.interfaces
import zope.publisher.interfaces.http
from zope.traversing.browser.absoluteurl import absoluteURL

from z3c.dav.coreproperties import ILockEntry, IDAVSupportedlock, \
     IActiveLock
import z3c.dav.interfaces

import interfaces
from manager import WEBDAV_LOCK_KEY

################################################################################
#
# zope.locking adapters.
#
################################################################################

class ExclusiveLockEntry(object):
    interface.implements(ILockEntry)

    lockscope = [u"exclusive"]
    locktype = [u"write"]


class SharedLockEntry(object):
    interface.implements(ILockEntry)

    lockscope = [u"shared"]
    locktype = [u"write"]


@component.adapter(interface.Interface, z3c.dav.interfaces.IWebDAVRequest)
@interface.implementer(IDAVSupportedlock)
def DAVSupportedlock(context, request):
    """
    This adapter retrieves the data for rendering in the `{DAV:}supportedlock`
    property. The `{DAV:}supportedlock` property provides a listing of lock
    capabilities supported by the resource.

    When their is no ITokenUtility registered with the system then we can't
    lock any content object and so this property is undefined.

      >>> DAVSupportedlock(None, None) is None
      True

      >>> from zope.locking import tokens
      >>> from zope.locking.utility import TokenUtility
      >>> util = TokenUtility()
      >>> component.getGlobalSiteManager().registerUtility(
      ...    util, zope.locking.interfaces.ITokenUtility)

    zope.locking supported both the exclusive and shared lock tokens.

      >>> slock = DAVSupportedlock(None, None)
      >>> len(slock.supportedlock)
      2
      >>> exclusive, shared = slock.supportedlock

      >>> exclusive.lockscope
      [u'exclusive']
      >>> exclusive.locktype
      [u'write']

      >>> shared.lockscope
      [u'shared']
      >>> shared.locktype
      [u'write']

    Cleanup

      >>> component.getGlobalSiteManager().unregisterUtility(
      ...    util, zope.locking.interfaces.ITokenUtility)
      True

    """
    utility = component.queryUtility(zope.locking.interfaces.ITokenUtility,
                                     context = context, default = None)
    if utility is None:
        return None
    return DAVSupportedlockAdapter()


class DAVSupportedlockAdapter(object):
    interface.implements(IDAVSupportedlock)
    component.adapts(interface.Interface,
                     z3c.dav.interfaces.IWebDAVRequest)

    @property
    def supportedlock(self):
        return [ExclusiveLockEntry(), SharedLockEntry()]


class DAVActiveLock(object):
    """
    This adapter is responsible for the data for the `{DAV:}activelock`
    XML element. This XML element occurs within the `{DAV:}lockdiscovery`
    property.

      >>> import datetime
      >>> import pytz
      >>> from cStringIO import StringIO
      >>> from BTrees.OOBTree import OOBTree
      >>> from zope.interface.verify import verifyObject
      >>> import zope.locking.utils
      >>> from zope.locking import tokens
      >>> from zope.locking.utility import TokenUtility
      >>> from z3c.dav.publisher import WebDAVRequest
      >>> import indirecttokens

      >>> def hackNow():
      ...     return datetime.datetime(2007, 4, 7, tzinfo = pytz.utc)
      >>> oldNow = zope.locking.utils.now
      >>> zope.locking.utils.now = hackNow

      >>> resource = DemoFolder()
      >>> request = WebDAVRequest(StringIO(''), {})

    Now register a ITokenUtility utility and lock the resource with it.

      >>> util = TokenUtility()
      >>> component.getGlobalSiteManager().registerUtility(
      ...    util, zope.locking.interfaces.ITokenUtility)

      >>> locktoken = tokens.ExclusiveLock(
      ...    resource, 'michael', datetime.timedelta(hours = 1))
      >>> locktoken = util.register(locktoken)

    DAVActiveLock is still None since their is no adapter from the demo
    content object to zope.locking.interfaces.ITokenBroker. This is part
    of the zope.locking installation that hasn't been completed yet.

      >>> activelock = DAVActiveLock(None, locktoken, resource, request)
      >>> IActiveLock.providedBy(activelock)
      True
      >>> verifyObject(IActiveLock, activelock)
      True

    Now test the data managed by the current activelock property.

      >>> activelock.lockscope
      [u'exclusive']
      >>> activelock.locktype
      [u'write']
      >>> activelock.timeout
      u'Second-3600'
      >>> activelock.lockroot
      '/dummy/'

    The depth attribute is required by the WebDAV specification. But this
    information is stored by the z3c.dav.lockingutils in the lock token's
    annotation. But if a lock token is taken out by an alternative Zope3
    application that uses the zope.locking package then this information will
    must likely not be set up. So this adapter should provide reasonable
    default values for this information. Later we will set up the lock
    token's annotation data to store this information. The data for the owner
    and locktoken XML elements are also stored on within the lock tokens
    annotation key but these XML elements are not required by the WebDAV
    specification so this data just defaults to None.

      >>> activelock.depth
      '0'
      >>> activelock.owner is None
      True
      >>> activelock.locktoken is None
      True

    Now if we try and render this information all the required fields, as
    specified by the WebDAV specification get rendered.

      >>> lockdiscovery = DAVLockdiscovery(resource, request)
      >>> davwidget = z3c.dav.properties.getWidget(
      ...    z3c.dav.coreproperties.lockdiscovery,
      ...    lockdiscovery, request)
      >>> print etree.tostring(davwidget.render()) #doctest:+XMLDATA
      <lockdiscovery xmlns="DAV:">
        <activelock>
          <lockscope><exclusive /></lockscope>
          <locktype><write /></locktype>
          <depth>0</depth>
          <timeout>Second-3600</timeout>
          <lockroot>/dummy/</lockroot>
        </activelock>
      </lockdiscovery>

    We use the lock tokens annotation to store the data for the owner, depth
    and locktoken attributes.

      >>> locktokendata=  locktoken.annotations[WEBDAV_LOCK_KEY] = OOBTree()
      >>> locktokendata['simpletoken'] = OOBTree()
      >>> locktokendata['simpletoken']['depth'] = 'testdepth'
      >>> locktokendata['simpletoken']['owner'] = '<owner xmlns="DAV:">Me</owner>'

    After updating the lock token's annotations we need to regenerate the
    activelock adapter so that the tokendata internal attribute is setup
    correctly.

      >>> activelock = DAVActiveLock(
      ...    'simpletoken', locktoken, resource, request)

    The owner attribute is not required by the WebDAV specification, but
    we can see it anyways, and similarly for the locktoken attribute.

      >>> activelock.owner
      '<owner xmlns="DAV:">Me</owner>'

    Each lock token on a resource as at most one `token` associated with it,
    but in order to display this information correctly we must return a
    a list with one item.

      >>> activelock.locktoken
      ['simpletoken']

      >>> lockdiscovery = DAVLockdiscovery(resource, request)
      >>> davwidget = z3c.dav.properties.getWidget(
      ...    z3c.dav.coreproperties.lockdiscovery,
      ...    lockdiscovery, request)
      >>> print etree.tostring(davwidget.render()) #doctest:+XMLDATA
      <lockdiscovery xmlns="DAV:">
        <activelock>
          <lockscope><exclusive /></lockscope>
          <locktype><write /></locktype>
          <depth>testdepth</depth>
          <owner>Me</owner>
          <timeout>Second-3600</timeout>
          <locktoken><href>simpletoken</href></locktoken>
          <lockroot>/dummy/</lockroot>
        </activelock>
      </lockdiscovery>

    Test the indirect locktoken. These are used when we try and lock a
    collection with the depth header set to `infinity`. These lock tokens
    share the same annotation information, expiry information and lock token,
    as the top level lock token.

      >>> resource['demo'] = Demo()
      >>> sublocktoken = indirecttokens.IndirectToken(
      ...    resource['demo'], locktoken)
      >>> sublocktoken = util.register(sublocktoken)

      >>> activelock = DAVActiveLock(
      ...    'simpletoken', sublocktoken, resource['demo'], request)
      >>> verifyObject(IActiveLock, activelock)
      True

      >>> activelock.lockscope
      [u'exclusive']
      >>> activelock.locktype
      [u'write']
      >>> activelock.depth
      'testdepth'
      >>> activelock.owner
      '<owner xmlns="DAV:">Me</owner>'
      >>> activelock.timeout
      u'Second-3600'
      >>> activelock.locktoken
      ['simpletoken']
      >>> activelock.lockroot
      '/dummy/'

    Now rendering the lockdiscovery DAV widget for this new resource we get
    the following.

      >>> lockdiscovery = DAVLockdiscovery(resource['demo'], request)
      >>> davwidget = z3c.dav.properties.getWidget(
      ...    z3c.dav.coreproperties.lockdiscovery,
      ...    lockdiscovery, request)
      >>> print etree.tostring(davwidget.render()) #doctest:+XMLDATA
      <lockdiscovery xmlns="DAV:">
        <activelock>
          <lockscope><exclusive /></lockscope>
          <locktype><write /></locktype>
          <depth>testdepth</depth>
          <owner>Me</owner>
          <timeout>Second-3600</timeout>
          <locktoken><href>simpletoken</href></locktoken>
          <lockroot>/dummy/</lockroot>
        </activelock>
      </lockdiscovery>

      >>> locktoken.end()

    Now a locktoken from an other application could be taken out on our
    demofolder that we know very little about. For example, a
    zope.locking.tokens.EndableFreeze` lock token. It should be displayed as
    an activelock on the resource but since we don't know if the scope of this
    token is an `{DAV:}exclusive` or `{DAV:}shared` (the only lock scopes
    currently supported by WebDAV), we will render this information as an
    empty XML element.

      >>> locktoken = tokens.EndableFreeze(
      ...    resource, datetime.timedelta(hours = 1))
      >>> locktoken = util.register(locktoken)

      >>> activelock = DAVActiveLock(None, locktoken, resource, request)
      >>> IActiveLock.providedBy(activelock)
      True

      >>> activelock.timeout
      u'Second-3600'
      >>> activelock.locktype
      [u'write']

    Now the locktoken is None so no WebDAV client should be able to a resource
    or more likely they shouldn't be able to take out a new lock on this
    resource, since the `IF` conditional header shored fail.

      >>> activelock.locktoken is None
      True

    So far so good. But the EndableFreeze token doesn't correspond to any
    lock scope known by this WebDAV implementation so when we try and access
    we just return a empty list. This ensures the `{DAV:}lockscope` element
    gets rendered by its IDAVWidget but it doesn't contain any information.

      >>> activelock.lockscope
      []
      >>> activelock.lockscope != z3c.dav.coreproperties.IActiveLock['lockscope'].missing_value
      True

    Rending this lock token we get the following.

      >>> lockdiscovery = DAVLockdiscovery(resource, request)
      >>> davwidget = z3c.dav.properties.getWidget(
      ...    z3c.dav.coreproperties.lockdiscovery,
      ...    lockdiscovery, request)
      >>> print etree.tostring(davwidget.render()) #doctest:+XMLDATA
      <lockdiscovery xmlns="DAV:">
        <activelock>
          <lockscope></lockscope>
          <locktype><write /></locktype>
          <depth>0</depth>
          <timeout>Second-3600</timeout>
          <lockroot>/dummy/</lockroot>
        </activelock>
      </lockdiscovery>

    Unlock the resource.

      >>> locktoken.end()

    Now not all lock tokens have a duration associated with them. In this
    case the timeout is None, as it is not fully required by the WebDAV
    specification and all the other attributes will have the default values
    as tested previously.

      >>> locktoken = tokens.ExclusiveLock(resource, 'michael')
      >>> locktoken = util.register(locktoken)

      >>> activelock = DAVActiveLock(None, locktoken, resource, request)
      >>> verifyObject(IActiveLock, activelock)
      True
      >>> activelock.timeout is None
      True

      >>> lockdiscovery = DAVLockdiscovery(resource, request)
      >>> davwidget = z3c.dav.properties.getWidget(
      ...    z3c.dav.coreproperties.lockdiscovery,
      ...    lockdiscovery, request)
      >>> print etree.tostring(davwidget.render()) #doctest:+XMLDATA
      <lockdiscovery xmlns="DAV:">
        <activelock>
          <lockscope><exclusive /></lockscope>
          <locktype><write /></locktype>
          <depth>0</depth>
          <lockroot>/dummy/</lockroot>
        </activelock>
      </lockdiscovery>

    Cleanup

      >>> zope.locking.utils.now = oldNow # undo time hack

      >>> component.getGlobalSiteManager().unregisterUtility(
      ...    util, zope.locking.interfaces.ITokenUtility)
      True

    """
    interface.implements(IActiveLock)

    def __init__(self, locktoken, token, context, request):
        self.context = self.__parent__ = context
        self._locktoken = locktoken
        self.token = token
        self.tokendata = token.annotations.get(
            WEBDAV_LOCK_KEY, {}).get(locktoken, {})
        self.request = request

    @property
    def lockscope(self):
        if interfaces.IIndirectToken.providedBy(self.token):
            roottoken = self.token.roottoken
        else:
            roottoken = self.token

        if zope.locking.interfaces.IExclusiveLock.providedBy(roottoken):
            return [u"exclusive"]
        elif zope.locking.interfaces.ISharedLock.providedBy(roottoken):
            return [u"shared"]

        return []

    @property
    def locktype(self):
        return [u"write"]

    @property
    def depth(self):
        return self.tokendata.get("depth", "0")

    @property
    def owner(self):
        return self.tokendata.get("owner", None)

    @property
    def timeout(self):
        remaining = self.token.remaining_duration
        if remaining is None:
            return None
        return u"Second-%d" % remaining.seconds

    @property
    def locktoken(self):
        return self._locktoken and [self._locktoken]

    @property
    def lockroot(self):
        if interfaces.IIndirectToken.providedBy(self.token):
            root = self.token.roottoken.context
        else:
            root = self.token.context

        return absoluteURL(root, self.request)


@component.adapter(
    interface.Interface, zope.publisher.interfaces.http.IHTTPRequest)
@interface.implementer(z3c.dav.coreproperties.IDAVLockdiscovery)
def DAVLockdiscovery(context, request):
    """
    This adapter is responsible for getting the data for the
    `{DAV:}lockdiscovery` property.

      >>> import datetime
      >>> from BTrees.OOBTree import OOBTree
      >>> from zope.interface.verify import verifyObject
      >>> from zope.locking import tokens
      >>> from zope.locking.utility import TokenUtility
      >>> from zope.locking.adapters import TokenBroker
      >>> from z3c.dav.publisher import WebDAVRequest
      >>> from cStringIO import StringIO
      >>> resource = Demo()
      >>> request = WebDAVRequest(StringIO(''), {})

      >>> DAVLockdiscovery(resource, request) is None
      True

      >>> util = TokenUtility()
      >>> component.getGlobalSiteManager().registerUtility(
      ...    util, zope.locking.interfaces.ITokenUtility)
      >>> component.getGlobalSiteManager().registerAdapter(DAVActiveLock,
      ...    (interface.Interface, z3c.dav.interfaces.IWebDAVRequest),
      ...     IActiveLock)
      >>> component.getGlobalSiteManager().registerAdapter(
      ...    TokenBroker, (interface.Interface,),
      ...    zope.locking.interfaces.ITokenBroker)

    The `{DAV:}lockdiscovery` is now defined for the resource but its value
    is None because the resource isn't locked yet.

      >>> lockdiscovery = DAVLockdiscovery(resource, request)
      >>> lockdiscovery is not None
      True
      >>> lockdiscovery.lockdiscovery is None
      True

      >>> token = tokens.ExclusiveLock(
      ...    resource, 'michael', datetime.timedelta(hours = 1))
      >>> token = util.register(token)
      >>> tokenannot = token.annotations[WEBDAV_LOCK_KEY] = OOBTree()
      >>> tokenannot['depth'] = 'testdepth'

      >>> lockdiscoveryview = DAVLockdiscovery(resource, request)
      >>> lockdiscovery = lockdiscoveryview.lockdiscovery
      >>> len(lockdiscovery)
      1
      >>> IActiveLock.providedBy(lockdiscovery[0])
      True
      >>> isinstance(lockdiscovery[0], DAVActiveLock)
      True

    Cleanup

      >>> component.getGlobalSiteManager().unregisterUtility(
      ...    util, zope.locking.interfaces.ITokenUtility)
      True
      >>> component.getGlobalSiteManager().unregisterAdapter(DAVActiveLock,
      ...    (interface.Interface, z3c.dav.interfaces.IWebDAVRequest),
      ...     IActiveLock)
      True
      >>> component.getGlobalSiteManager().unregisterAdapter(
      ...    TokenBroker, (interface.Interface,),
      ...    zope.locking.interfaces.ITokenBroker)
      True

    """
    utility = component.queryUtility(zope.locking.interfaces.ITokenUtility)
    if utility is None:
        return None
    return DAVLockdiscoveryAdapter(context, request, utility)


class DAVLockdiscoveryAdapter(object):
    interface.implements(z3c.dav.coreproperties.IDAVLockdiscovery)
    component.adapts(interface.Interface,
                     z3c.dav.interfaces.IWebDAVRequest)

    def __init__(self, context, request, utility):
        self.context = context
        self.request = request
        self.utility = utility

    @property
    def lockdiscovery(self):
        token = self.utility.get(self.context)
        if token is None:
            return None

        activelocks = []
        for locktoken in token.annotations.get(WEBDAV_LOCK_KEY, {}).keys():
            if locktoken != "principal_ids":
                activelocks.append(DAVActiveLock(locktoken, token,
                                                 self.context, self.request))
        if activelocks:
            return activelocks

        # Probable a non-webdav client / application created this lock.
        # We probable need an other active lock implementation to handle
        # this case.
        return [DAVActiveLock(None, token, self.context, self.request)]
