from setuptools import setup, find_packages

setup(name = "z3c.davapp.zopelocking",
      version = "0.9",
      author = "Michael Kerrin",
      author_email = "michael.kerrin@openapp.ie",
      url = "http://launchpad.net/z3c.dav",
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

      include_package_data = True,
      zip_safe = False)
