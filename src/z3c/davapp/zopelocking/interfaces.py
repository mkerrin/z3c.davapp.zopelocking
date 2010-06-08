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

import zope.interface
import zope.locking.interfaces


class IIndirectToken(zope.locking.interfaces.IToken,
                     zope.locking.interfaces.IEndable):
    """
    An indirect lock token a token taken out on a content object against
    another lock token, called the root token. All annotations, utility,
    principal_ids and start end times are stored on the `roottoken`. With
    a indirect locktoken acting as a proxy to the information stored there.

    When ever the root lock token or any indirect lock tokens taken out
    against it are unlocked then all tokens in this set are unlocked. It is
    the same same with updating information. Data updated on a indirect
    lock token is stored in the root token and then when ever an other
    indirect lock token is queried for information we get the updated data.
    """

    roottoken = zope.interface.Attribute("""
    Return the root lock token against which this token is locked.
    """)
