from setuptools import setup, find_packages

setup(name = "z3c.davapp.zopelocking",
      version = "1.0b1",
      author = "Michael Kerrin",
      author_email = "michael.kerrin@openapp.ie",
      url = "http://launchpad.net/z3c.dav",
      description = "WebDAV locking support using zope.locking",
      long_description = (
          open("README.txt").read() +
          "\n\n" +
          open("CHANGES.txt").read()),
      license = "ZPL",
      classifiers = ["Environment :: Web Environment",
                     "Intended Audience :: Developers",
                     "License :: OSI Approved :: Zope Public License",
                     "Programming Language :: Python",
                     "Framework :: Zope3",
                     ],

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
