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
"""
import UserDict
import unittest

import zope.component
import zope.interface
from zope.testing import doctest
from zope.security.testing import Principal
from zope.publisher.browser import TestRequest
from zope.security.management import newInteraction, endInteraction, \
     queryInteraction
import zope.event
from zope.traversing.interfaces import IPhysicallyLocatable
from zope.app.testing import placelesssetup
from zope.component.interfaces import IComponentLookup
from zope.app.component.site import SiteManagerAdapter
from zope.app.container.interfaces import IContained, IContainer
import zope.app.keyreference.interfaces
import zope.annotation.interfaces
import zope.traversing.browser.interfaces

import z3c.etree.testing

class IDemo(IContained):
    "a demonstration interface for a demonstration class"


class IDemoFolder(IContained, IContainer):
    "a demostration interface for a demostration folder class"


class Demo(object):
    zope.interface.implements(IDemo,
                              zope.annotation.interfaces.IAttributeAnnotatable)

    __parent__ = __name__ = None


class DemoFolder(UserDict.UserDict):
    zope.interface.implements(IDemoFolder)

    __parent__ = __name__ = None

    def __init__(self, parent = None, name = u''):
        UserDict.UserDict.__init__(self)
        self.__parent__ = parent
        self.__name__   = name

    def __setitem__(self, key, value):
        value.__name__ = key
        value.__parent__ = self
        self.data[key] = value


class PhysicallyLocatable(object):
    zope.interface.implements(IPhysicallyLocatable)

    def __init__(self, context):
        self.context = context

    def getRoot(self):
        return root

    def getPath(self):
        return '/' + self.context.__name__


class DemoKeyReference(object):
    _class_counter = 0
    zope.interface.implements(zope.app.keyreference.interfaces.IKeyReference)

    def __init__(self, context):
        self.context = context
        class_ = type(self)
        self._id = getattr(context, "__demo_key_reference__", None)
        if self._id is None:
            self._id = class_._class_counter
            context.__demo_key_reference__ = self._id
            class_._class_counter += 1

    key_type_id = "zope.app.dav.lockingutils.DemoKeyReference"

    def __call__(self):
        return self.context

    def __hash__(self):
        return (self.key_type_id, self._id)

    def __cmp__(self, other):
        if self.key_type_id == other.key_type_id:
            return cmp(self._id, other._id)
        return cmp(self.key_type_id, other.key_type_id)


class DemoAbsoluteURL(object):
    zope.interface.implements(zope.traversing.browser.interfaces.IAbsoluteURL)

    def __init__(self, context, request):
        self.context = context

    def __str__(self):
        ob = self.context
        url = ""
        while ob is not None:
            url += "/dummy"
            ob = ob.__parent__
        if IDemoFolder.providedBy(self.context):
            url += "/"
        return url

    __call__ = __str__


def lockingSetUp(test):
    placelesssetup.setUp(test)
    z3c.etree.testing.etreeSetup(test)

    # create principal
    participation = TestRequest(environ = {"REQUEST_METHOD": "PUT"})
    participation.setPrincipal(Principal("michael"))
    if queryInteraction() is not None:
        queryInteraction().add(participation)
    else:
        newInteraction(participation)

    events = test.globs["events"] = []
    zope.event.subscribers.append(events.append)

    gsm = zope.component.getGlobalSiteManager()

    gsm.registerAdapter(DemoKeyReference,
                        (IDemo,),
                        zope.app.keyreference.interfaces.IKeyReference)
    gsm.registerAdapter(PhysicallyLocatable, (Demo,))
    gsm.registerAdapter(PhysicallyLocatable, (DemoFolder,))
    gsm.registerAdapter(DemoKeyReference, (IDemoFolder,),
                        zope.app.keyreference.interfaces.IKeyReference)
    gsm.registerAdapter(SiteManagerAdapter,
                        (zope.interface.Interface,), IComponentLookup)
    gsm.registerAdapter(DemoAbsoluteURL,
                        (IDemo, zope.interface.Interface),
                        zope.traversing.browser.interfaces.IAbsoluteURL)
    gsm.registerAdapter(DemoAbsoluteURL,
                        (IDemoFolder, zope.interface.Interface),
                        zope.traversing.browser.interfaces.IAbsoluteURL)

    # register some IDAVWidgets so that we can render the activelock and
    # supportedlock widgets.
    gsm.registerAdapter(z3c.dav.widgets.ListDAVWidget,
                        (zope.schema.interfaces.IList,
                         z3c.dav.interfaces.IWebDAVRequest))
    gsm.registerAdapter(z3c.dav.widgets.ObjectDAVWidget,
                        (zope.schema.interfaces.IObject,
                         z3c.dav.interfaces.IWebDAVRequest))
    gsm.registerAdapter(z3c.dav.widgets.TextDAVWidget,
                        (zope.schema.interfaces.IText,
                         z3c.dav.interfaces.IWebDAVRequest))
    gsm.registerAdapter(z3c.dav.properties.OpaqueWidget,
                        (z3c.dav.properties.DeadField,
                         z3c.dav.interfaces.IWebDAVRequest))
    gsm.registerAdapter(z3c.dav.widgets.TextDAVWidget,
                        (zope.schema.interfaces.IURI,
                         z3c.dav.interfaces.IWebDAVRequest))

    # expose these classes to the test
    test.globs["Demo"] = Demo
    test.globs["DemoFolder"] = DemoFolder


def lockingTearDown(test):
    placelesssetup.tearDown(test)
    z3c.etree.testing.etreeTearDown(test)

    events = test.globs.pop("events")
    assert zope.event.subscribers.pop().__self__ is events
    del events[:] # being paranoid

    del test.globs["Demo"]
    del test.globs["DemoFolder"]

    gsm = zope.component.getGlobalSiteManager()

    gsm.unregisterAdapter(DemoKeyReference,
                          (IDemo,),
                          zope.app.keyreference.interfaces.IKeyReference)
    gsm.unregisterAdapter(PhysicallyLocatable, (Demo,))
    gsm.unregisterAdapter(PhysicallyLocatable, (DemoFolder,))
    gsm.unregisterAdapter(DemoKeyReference, (IDemoFolder,),
                          zope.app.keyreference.interfaces.IKeyReference)
    gsm.unregisterAdapter(SiteManagerAdapter,
                          (zope.interface.Interface,), IComponentLookup)
    gsm.unregisterAdapter(DemoAbsoluteURL,
                          (IDemo, zope.interface.Interface),
                          zope.traversing.browser.interfaces.IAbsoluteURL)
    gsm.unregisterAdapter(DemoAbsoluteURL,
                          (IDemoFolder, zope.interface.Interface),
                          zope.traversing.browser.interfaces.IAbsoluteURL)

    gsm.unregisterAdapter(z3c.dav.widgets.ListDAVWidget,
                          (zope.schema.interfaces.IList,
                           z3c.dav.interfaces.IWebDAVRequest))
    gsm.unregisterAdapter(z3c.dav.widgets.ObjectDAVWidget,
                          (zope.schema.interfaces.IObject,
                           z3c.dav.interfaces.IWebDAVRequest))
    gsm.unregisterAdapter(z3c.dav.widgets.TextDAVWidget,
                          (zope.schema.interfaces.IText,
                           z3c.dav.interfaces.IWebDAVRequest))
    gsm.unregisterAdapter(z3c.dav.properties.OpaqueWidget,
                          (z3c.dav.properties.DeadField,
                           z3c.dav.interfaces.IWebDAVRequest))
    gsm.unregisterAdapter(z3c.dav.widgets.TextDAVWidget,
                          (zope.schema.interfaces.IURI,
                           z3c.dav.interfaces.IWebDAVRequest))

    endInteraction()


def test_suite():
    return unittest.TestSuite((
        doctest.DocTestSuite("z3c.davapp.zopelocking.properties",
                             checker = z3c.etree.testing.xmlOutputChecker,
                             setUp = lockingSetUp,
                             tearDown = lockingTearDown),
        doctest.DocTestSuite("z3c.davapp.zopelocking.manager",
                             checker = z3c.etree.testing.xmlOutputChecker,
                             setUp = lockingSetUp,
                             tearDown = lockingTearDown),
        doctest.DocTestSuite("z3c.davapp.zopelocking.indirecttokens",
                             checker = z3c.etree.testing.xmlOutputChecker,
                             setUp = lockingSetUp,
                             tearDown = lockingTearDown),
        ))
