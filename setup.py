from setuptools import setup, find_packages

setup(name = "z3c.davapp.zopelocking",
      version = "0.1",
      author = "Michael Kerrin",
      author_email = "michael.kerrin@openapp.ie",
      url = "http://svn.zope.org/",
      description = "WebDAV locking support using zope.locking",
      license = "ZPL",

      packages = find_packages("src"),
      package_dir = {"": "src"},
      namespace_packages = ["z3c", "z3c.davapp"],
      install_requires = ["setuptools",
                          "z3c.dav",
                          "zope.locking",
                          "zope.app.keyreference",
                          "zc.i18n",
                          ],

      extras_require = dict(test = ["cElementTree"]),

      include_package_data = True,
      zip_safe = False)
