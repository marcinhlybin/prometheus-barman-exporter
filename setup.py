from setuptools import setup

setup(name='barman_exporter',
      version='1.0.10',
      description='Barman exporter for Prometheus',
      long_description='Barman exporter for Prometheus. Full description at https://github.com/ahes/prometheus-barman-exporter',
      url='https://github.com/ahes/prometheus-barman-exporter',
      author='Marcin Hlybin',
      author_email='marcin.hlybin@gmail.com',
      license='MIT',
      packages=['barman_exporter'],
      keywords='prometheus barman exporter barman-exporter',
      entry_points={
          'console_scripts': ['barman-exporter=barman_exporter.barman_exporter:main'],
      },
      install_requires=[
          'prometheus-client',
          'sh'
      ],
      zip_safe=False)
