##############################################################################
#
# Copyright (c) 2007 Zope Corporation and Contributors.
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
Provides support for create indirect locktokens as suggested by the WebDAV
specification.
"""

import persistent
import zope.component
import zope.interface
import zope.locking.interfaces
import zope.locking.tokens
from zope.app.keyreference.interfaces import IKeyReference

import interfaces

INDIRECT_INDEX_KEY = 'zope.app.dav.lockingutils'

class IndirectToken(persistent.Persistent):
    """

    Most of these tests have being copied from the README.txt file in
    zope.locking

    Some initial setup including creating some demo content.

      >>> from zope.locking import utility, utils
      >>> util = utility.TokenUtility()
      >>> zope.component.getGlobalSiteManager().registerUtility(
      ...    util, zope.locking.interfaces.ITokenUtility)

    Setup some content to test on.

      >>> demofolder = DemoFolder(None, 'demofolderroot')
      >>> demofolder['demo1'] = Demo()
      >>> demofolder['demofolder1'] = DemoFolder()
      >>> demofolder['demofolder1']['demo'] = Demo()

    Lock the root folder with an exclusive lock.

      >>> lockroot = zope.locking.tokens.ExclusiveLock(demofolder, 'michael')
      >>> res = util.register(lockroot)

    Now indirectly all the descended objects of the root folder against the
    exclusive lock token we used to lock this folder with.

      >>> lock1 = IndirectToken(demofolder['demo1'], lockroot)
      >>> lock2 = IndirectToken(demofolder['demofolder1'], lockroot)
      >>> lock3 = IndirectToken(demofolder['demofolder1']['demo'], lockroot)
      >>> res1 = util.register(lock1)
      >>> lock1 is util.get(demofolder['demo1'])
      True
      >>> res2 = util.register(lock2)
      >>> lock2 is util.get(demofolder['demofolder1'])
      True
      >>> res3 = util.register(lock3)
      >>> lock3 is util.get(demofolder['demofolder1']['demo'])
      True

    Make sure that the lockroot contains an index of all the toekns locked
    against in its annotations

      >>> len(lockroot.annotations[INDIRECT_INDEX_KEY])
      3

    Check that the IEndable properties are None

      >>> res1.expiration == lockroot.expiration == None
      True
      >>> res1.duration == lockroot.duration == None
      True
      >>> res1.duration == lockroot.remaining_duration == None
      True
      >>> res1.started == lockroot.started
      True
      >>> lockroot.started is not None
      True

    All the indirect locktokens and the lookroot share the same annotations

      >>> lockroot.annotations[u'webdav'] = u'test webdav indirect locking'
      >>> res1.annotations[u'webdav']
      u'test webdav indirect locking'

    All the lock tokens have the same principals

      >>> list(res1.principal_ids)
      ['michael']
      >>> list(lockroot.principal_ids)
      ['michael']

    None of the locks have ended yet, and they share the same utility.

      >>> res1.ended is None
      True
      >>> lockroot.ended is None
      True
      >>> lockroot.utility is res1.utility
      True

    Expire the lock root

      >>> now = utils.now()
      >>> res3.end()

    Now all the descendent objects of the lockroot and the lockroot itself
    are unlocked.

      >>> util.get(demofolder) is None
      True
      >>> util.get(demofolder['demo1']) is None
      True
      >>> util.get(demofolder['demofolder1']['demo']) is None
      True

    Also all the tokens has ended after now.

      >>> lock1.ended is not None
      True
      >>> lock2.ended > now
      True
      >>> lock1.ended is lock2.ended
      True
      >>> lock3.ended is lockroot.ended
      True

    Test the event subscribers.

      >>> ev = events[-1]
      >>> zope.locking.interfaces.ITokenEndedEvent.providedBy(ev)
      True
      >>> len(lockroot.annotations[INDIRECT_INDEX_KEY])
      3
      >>> ev.object is lockroot
      True
      >>> removeEndedTokens(lockroot, ev)
      >>> len(lockroot.annotations[INDIRECT_INDEX_KEY])
      0

    Test all the endable attributes

      >>> import datetime
      >>> one = datetime.timedelta(hours = 1)
      >>> two = datetime.timedelta(hours = 2)
      >>> three = datetime.timedelta(hours = 3)
      >>> four = datetime.timedelta(hours = 4)
      >>> lockroot = zope.locking.tokens.ExclusiveLock(
      ...    demofolder, 'john', three)
      >>> dummy = util.register(lockroot)
      >>> indirect1 = IndirectToken(demofolder['demo1'], lockroot)
      >>> dummy = util.register(indirect1)
      >>> indirect1.duration
      datetime.timedelta(0, 10800)
      >>> lockroot.duration == indirect1.duration
      True
      >>> indirect1.ended is None
      True
      >>> indirect1.expiration == indirect1.started + indirect1.duration
      True

    Now try to 

      >>> indirect1.expiration = indirect1.started + one
      >>> indirect1.expiration == indirect1.started + one
      True
      >>> indirect1.expiration == lockroot.expiration
      True
      >>> indirect1.duration == one
      True

    Now test changing the duration attribute

      >>> indirect1.duration = four
      >>> indirect1.duration == lockroot.duration
      True
      >>> indirect1.duration
      datetime.timedelta(0, 14400)

    Now check the remain_duration code

      >>> import pytz
      >>> def hackNow():
      ...     return (datetime.datetime.now(pytz.utc) +
      ...             datetime.timedelta(hours=2))
      ...
      >>> import zope.locking.utils
      >>> oldNow = zope.locking.utils.now
      >>> zope.locking.utils.now = hackNow # make code think it's 2 hours later
      >>> indirect1.duration
      datetime.timedelta(0, 14400)
      >>> two >= indirect1.remaining_duration >= one
      True
      >>> indirect1.remaining_duration -= one
      >>> one >= indirect1.remaining_duration >= datetime.timedelta()
      True
      >>> three + datetime.timedelta(minutes = 1) >= indirect1.duration >= three
      True

    Since we modified the remaining_duration attribute a IExpirationChagedEvent
    should have being fired.
      
      >>> ev = events[-1]
      >>> from zope.interface.verify import verifyObject
      >>> from zope.locking.interfaces import IExpirationChangedEvent
      >>> verifyObject(IExpirationChangedEvent, ev)
      True
      >>> ev.object is lockroot
      True

    Now pretend that it is a day later, the indirect token and the lock root
    will have timed out sliently.

      >>> def hackNow():
      ...     return (
      ...         datetime.datetime.now(pytz.utc) + datetime.timedelta(days=1))
      ...
      >>> zope.locking.utils.now = hackNow # make code think it is a day later
      >>> indirect1.ended == indirect1.expiration
      True
      >>> lockroot.ended == indirect1.ended
      True
      >>> util.get(demofolder['demo1']) is None
      True
      >>> util.get(demofolder['demo1'], util) is util
      True
      >>> indirect1.remaining_duration == datetime.timedelta()
      True
      >>> indirect1.end()
      Traceback (most recent call last):
      ...
      EndedError

    Once a lock has ended, the timeout can no longer be changed.

      >>> indirect1.duration = datetime.timedelta(days=2)
      Traceback (most recent call last):
      ...
      EndedError

    Now undo our hack.

      >>> zope.locking.utils.now = oldNow # undo the hack
      >>> indirect1.end() # really end the token
      >>> util.get(demofolder) is None
      True

    Now test the simple SharedLock with an indirect token.

      >>> lockroot = zope.locking.tokens.SharedLock(
      ...    demofolder, ('john', 'mary'))
      >>> dummy = util.register(lockroot)
      >>> sharedindirect = IndirectToken(demofolder['demo1'], lockroot)
      >>> dummy = util.register(sharedindirect)
      >>> sorted(sharedindirect.principal_ids)
      ['john', 'mary']
      >>> sharedindirect.add(('jane',))
      >>> sorted(lockroot.principal_ids)
      ['jane', 'john', 'mary']
      >>> sorted(sharedindirect.principal_ids)
      ['jane', 'john', 'mary']
      >>> sharedindirect.remove(('mary',))
      >>> sorted(sharedindirect.principal_ids)
      ['jane', 'john']
      >>> sorted(lockroot.principal_ids)
      ['jane', 'john']
      >>> lockroot.remove(('jane',))
      >>> sorted(sharedindirect.principal_ids)
      ['john']
      >>> sorted(lockroot.principal_ids)
      ['john']
      >>> sharedindirect.remove(('john',))
      >>> util.get(demofolder) is None
      True
      >>> util.get(demofolder['demo1']) is None
      True

    Test using the shared lock token methods on a non shared lock

      >>> lockroot = zope.locking.tokens.ExclusiveLock(demofolder, 'john')
      >>> dummy = util.register(lockroot)
      >>> indirect1 = IndirectToken(demofolder['demo1'], lockroot)
      >>> dummy = util.register(indirect1)
      >>> dummy is indirect1
      True
      >>> dummy.add('john')
      Traceback (most recent call last):
      ...
      TypeError: can't add a principal to a non-shared token
      >>> dummy.remove('michael')
      Traceback (most recent call last):
      ...
      TypeError: can't add a principal to a non-shared token

    Setup with wrong utility.

      >>> util2 = utility.TokenUtility()
      >>> roottoken = zope.locking.tokens.ExclusiveLock(demofolder, 'michael2')
      >>> roottoken = util2.register(roottoken)
      >>> roottoken.utility == util2
      True

      >>> indirecttoken = IndirectToken(demofolder['demo1'], roottoken)
      >>> indirecttoken = util2.register(indirecttoken)
      >>> indirecttoken.utility is util2
      True
      >>> indirecttoken.utility = util
      Traceback (most recent call last):
      ...
      ValueError: cannot reset utility
      >>> indirecttoken = IndirectToken(demofolder['demo1'], roottoken)
      >>> indirecttoken.utility = util
      Traceback (most recent call last):
      ...
      ValueError: Indirect tokens must be registered with the same utility has the root token

    Cleanup test.

      >>> zope.component.getGlobalSiteManager().unregisterUtility(
      ...    util, zope.locking.interfaces.ITokenUtility)
      True

    """
    zope.interface.implements(interfaces.IIndirectToken)

    def __init__(self, target, token):
        self.context = self.__parent__ = target
        self.roottoken = token

    _utility = None
    @apply
    def utility():
        # IAbstractToken - this is the only hook I can find since
        # it represents the lock utility in charge of this lock.
        def get(self):
            return self._utility
        def set(self, value):
            if self._utility is not None:
                if value is not self._utility:
                    raise ValueError("cannot reset utility")
            else:
                assert zope.locking.interfaces.ITokenUtility.providedBy(value)
                root = self.roottoken
                if root.utility != value:
                    raise ValueError("Indirect tokens must be registered with" \
                                     " the same utility has the root token")
                index = root.annotations.get(INDIRECT_INDEX_KEY, None)
                if index is None:
                    index = root.annotations[INDIRECT_INDEX_KEY] = \
                            zope.locking.tokens.AnnotationsMapping()
                    index.__parent__ = root
                key_ref = IKeyReference(self.context)
                assert index.get(key_ref, None) is None, \
                       "context is already locked"
                index[key_ref] = self
                self._utility = value
        return property(get, set)

    @property
    def principal_ids(self):
        # IAbstractToken
        return self.roottoken.principal_ids

    @property
    def started(self):
        # IAbstractToken
        return self.roottoken.started

    @property
    def annotations(self):
        # See IToken
        return self.roottoken.annotations

    def add(self, principal_ids):
        # ISharedLock
        if not zope.locking.interfaces.ISharedLock.providedBy(self.roottoken):
            raise TypeError, "can't add a principal to a non-shared token"
        return self.roottoken.add(principal_ids)

    def remove(self, principal_ids):
        # ISharedLock
        if not zope.locking.interfaces.ISharedLock.providedBy(self.roottoken):
            raise TypeError, "can't add a principal to a non-shared token"
        return self.roottoken.remove(principal_ids)

    @property
    def ended(self):
        # IEndable
        return self.roottoken.ended

    @apply
    def expiration(): # XXX - needs testing
        # IEndable
        def get(self):
            return self.roottoken.expiration
        def set(self, value):
            self.roottoken.expiration = value
        return property(get, set)

    @apply
    def duration(): # XXX - needs testing
        # IEndable
        def get(self):
            return self.roottoken.duration
        def set(self, value):
            self.roottoken.duration = value
        return property(get, set)

    @apply
    def remaining_duration():
        # IEndable
        def get(self):
            return self.roottoken.remaining_duration
        def set(self, value):
            self.roottoken.remaining_duration = value
        return property(get, set)

    def end(self):
        # IEndable
        return self.roottoken.end()


@zope.component.adapter(zope.locking.interfaces.IEndableToken,
                        zope.locking.interfaces.ITokenEndedEvent)
def removeEndedTokens(object, event):
    """subscriber handler for ITokenEndedEvent"""
    assert zope.locking.interfaces.ITokenEndedEvent.providedBy(event)
    roottoken = event.object
    assert not interfaces.IIndirectToken.providedBy(roottoken)
    index = roottoken.annotations.get(INDIRECT_INDEX_KEY, {})
    # read the whole index in memory so that we correctly loop over all the
    # items in this list.
    indexItems = list(index.items())
    for key_ref, token in indexItems:
        # token has ended so it should be removed via the register method
        roottoken.utility.register(token)
        del index[key_ref]
