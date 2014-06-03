# -*- coding: UTF-8 -*-
__author__ = 'jun.han'

import smtplib
import getpass
import time
import subprocess
import tarfile
import shutil
import ConfigParser
import git
import glob
import re
import sys
from email import encoders
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from myutils import *


class GenieBuilder(object):
    def __init__(self):
        os.chdir(os.path.dirname(sys.argv[0]))
        config = ConfigParser.ConfigParser()
        config_file_name = os.path.splitext(__file__)[0] + '.ini'
        encoding = get_encoding(config_file_name)
        config.readfp(codecs.open(config_file_name, "r", encoding))

        self.log_fp = None
        self.tarball_path = None
        self.work_dir = os.getcwd()

        self.genie_base_dir = os.path.normpath(config.get('base', 'genie_base_dir'))
        self.plugin_dir = os.path.normpath(self.genie_base_dir + '\\' + config.get('base', 'plugin_dir'))
        self.qt_runtime_dir = os.path.normpath(config.get('base', 'qt_runtime_dir'))
        self.win32_plugins = config.get('base', 'win32_plugins').split(':')
        self.mingw32_plugins = config.get('base', 'mingw32_plugins').split(':')
        self.files_check_list = config.get('base', 'files_check_list').split(':')

        self.smtp_server, self.smtp_server_port = config.get('mail', 'smtp_server').split(':')
        self.admin_email = config.get('mail', 'admin_email')
        self.pass_in_conf = config.get('mail', 'pass_in_conf')
        if self.pass_in_conf == '1':
            self.mail_pass = config.get('mail', 'password')
        else:
            self.mail_pass = getpass.getpass('Please input your mail password:')

        self.ssl_enable = config.get('mail', 'SSL_enable')
        if self.ssl_enable == '1':
            self.mail_server = smtplib.SMTP_SSL(self.smtp_server, self.smtp_server_port)
        else:
            self.mail_server = smtplib.SMTP(self.smtp_server, self.smtp_server_port)

        self.deploy_path = config.get('deploy', 'deploy_path')
        self.git_path = config.get('git', 'git_path')

        if config.get('build_tools', 'enable') == '1':
            self.devenv = config.get('build_tools', 'devenv')
            self.qmake = config.get('build_tools', 'qmake')
            self.mingw32_make = config.get('build_tools', 'mingw32-make')
            self.makensis = config.get('build_tools', 'makensis')
        else:
            self.devenv = 'devenv'
            self.qmake = 'qmake'
            self.mingw32_make = 'mingw32-make'
            self.makensis = 'makensis'

        #multi jobs
        jobs = 1 if 'NUMBER_OF_PROCESSORS' not in os.environ else int(os.environ['NUMBER_OF_PROCESSORS'])
        self.mingw32_make += ' -j%d' % jobs

        #init git command line
        self.git = git.Git(self.genie_base_dir)
        self.build_logs_dir = r'%s\buildlogs\%s' % (self.genie_base_dir, time.strftime('%Y%m%d%H%M%S',
                                                                                       time.localtime()))
        if not os.path.exists(self.build_logs_dir):
            os.makedirs(self.build_logs_dir)

    def get_source(self):
        print self.git_exe('git pull')

    def git_exe(self, cmd):
        old_path = os.getcwd()
        os.chdir(self.git_path)
        ret = self.git.execute(cmd)
        os.chdir(old_path)
        return ret

    def compile(self):

        #vc
        for each in self.win32_plugins:
            cmd = r'"%s" %s\%s\%s.sln /Rebuild "Release|Win32"' % (self.devenv, self.plugin_dir, each, each)
            process = subprocess.Popen(cmd)
            process.wait()
            cmd = r'"%s" %s\%s\%s.sln /Rebuild "Release|x64"' % (self.devenv, self.plugin_dir, each, each)
            process = subprocess.Popen(cmd)
            process.wait()

        print os.getcwd()
        #mingw
        for each in self.mingw32_plugins:
            cwd = r'%s\%s' % (self.plugin_dir, each)
            os.chdir(cwd)
            self.log_fp = open('%s\\%s.log' % (self.build_logs_dir, each.replace('\\', '_')), 'w+')

            os.system(self.qmake)
            os.system("%s -f Makefile.Release clean" % self.mingw32_make)
            process = subprocess.Popen("%s release" % self.mingw32_make, stdout=self.log_fp, stderr=self.log_fp)
            process.wait()

            self.log_fp.close()
            self.log_fp = None
            if process.returncode != 0:
                return each

    def mail_on_success(self):
        email = MIMEMultipart()
        email['From'] = self.admin_email
        email['To'] = self.admin_email
        email['Subject'] = 'Build Report: SUCCESS'

        fp = open(os.path.join(self.work_dir, 'mail_template_sucess.txt'), 'r')
        mail_template = fp.read() % {'project': self.genie_base_dir.split('\\')[-1],
                                     'admin': self.admin_email,
                                     'deployfile': self.deploy_path + "\\" + os.path.basename(self.tarball_path)}
        fp.close()
        body = MIMEText(mail_template, 'plain')
        email.attach(body)

        self.mail_server.connect(self.smtp_server, self.smtp_server_port)
        self.mail_server.ehlo_or_helo_if_needed()
        self.mail_server.login(self.admin_email, self.mail_pass)
        self.mail_server.sendmail(self.admin_email, self.admin_email, email.as_string())

    def mail_on_error(self, mod):
        print mod
        if not mod.startswith('..'):
            git_cmd = "git log --pretty=format:%%ae -1 %s/%s" % (self.plugin_dir.split('\\')[-1], mod)
        else:
            git_cmd = "git log --pretty=format:%%ae -1 %s" % mod.split('\\')[-1]
        print git_cmd
        last_author_email = self.git_exe(git_cmd)
        print last_author_email

        #mail header
        email = MIMEMultipart()
        email['From'] = self.admin_email
        email['To'] = last_author_email
        email['Subject'] = 'Build Report: FAIL'

        #mail body
        fp = open(os.path.join(self.work_dir, 'mail_template_failure.txt'), 'r')
        mail_template = fp.read() % {'author': last_author_email.split('@')[0],
                                     'project': self.genie_base_dir.split('\\')[-1],
                                     'module': mod,
                                     'admin': self.admin_email}
        fp.close()
        body = MIMEText(mail_template, 'plain')
        email.attach(body)

        #mail attachments
        tarball_path = self.make_log_tarball()
        fp = open(tarball_path, 'rb')
        attachment = MIMEBase('application', 'octet-stream')
        attachment.set_payload(fp.read())
        fp.close()
        encoders.encode_base64(attachment)
        attachment.add_header('Content-Disposition', 'attachment', filename=tarball_path.split('\\')[-1])
        email.attach(attachment)

        self.mail_server.connect(self.smtp_server, self.smtp_server_port)
        self.mail_server.ehlo_or_helo_if_needed()
        self.mail_server.login(self.admin_email, self.mail_pass)
        self.mail_server.sendmail(self.admin_email, last_author_email, email.as_string())

    def package(self):
        nsis_genie_bin_dir = self.genie_base_dir + "\\Nsis\\genie\\bin"
        if os.path.isdir(nsis_genie_bin_dir):
            shutil.rmtree(nsis_genie_bin_dir)
            time.sleep(3)
        os.makedirs(nsis_genie_bin_dir)
        #copy files into dst dir
        file_to_copy = glob.glob(self.genie_base_dir + "\\bin\\*.dll")
        for each in file_to_copy:
            shutil.copy(each, nsis_genie_bin_dir)

        file_to_copy = glob.glob(self.genie_base_dir + "\\bin\\*.exe")
        for each in file_to_copy:
            shutil.copy(each, nsis_genie_bin_dir)

        if os.path.isdir(nsis_genie_bin_dir + "\\drivers"):
            shutil.rmtree(nsis_genie_bin_dir + "\\drivers")

        if os.path.isdir(self.genie_base_dir + "\\Nsis\\drivers"):
            shutil.copytree(self.genie_base_dir + "\\Nsis\\drivers", nsis_genie_bin_dir + "\\drivers")

        if os.path.isdir(self.qt_runtime_dir):
            for each in os.listdir(self.qt_runtime_dir):
                source = os.path.join(self.qt_runtime_dir, each)
                if os.path.isfile(source):
                    shutil.copy(source, nsis_genie_bin_dir)

        if not self.check_files(nsis_genie_bin_dir):
            return False

        self.log_fp = open(os.path.join(self.build_logs_dir, "Nsis.log"), "w+")
        process = subprocess.Popen(r'"%s" %s' % (self.makensis, self.genie_base_dir + "\\Nsis\\Genie_Setup.nsi"),
                                   stdout=self.log_fp, stderr=self.log_fp)
        process.wait()
        self.log_fp.flush()
        self.log_fp.seek(0, os.SEEK_SET)
        output = self.log_fp.read()
        self.log_fp.close()
        self.log_fp = None

        print output
        ret = re.search(r'^Output:[^"]+"([^"]+)', output, re.M)
        self.tarball_path = ret.group(1) + ".tgz"
        tarball = tarfile.open(self.tarball_path, "w:gz")
        os.chdir(os.path.dirname(ret.group(1)))
        tarball.add(os.path.basename(ret.group(1)))
        tarball.close()

        return True

    def check_files(self, nsis_genie_bin_dir):
        for each in self.files_check_list:
            if not os.path.exists(nsis_genie_bin_dir + "\\" + each):
                print "Cannot find %s! Packaging failed!" % (nsis_genie_bin_dir + "\\" + each)
                return False
        print "Files are checked over!"
        return True

    def deploy(self):
        dst_file = self.deploy_path + "\\" + os.path.basename(self.tarball_path)
        src_fp = open(self.tarball_path, "rb")
        dst_fp = open(dst_file, "wb+")
        dst_fp.write(src_fp.read())
        dst_fp.close()
        src_fp.close()

    def make_log_tarball(self):
        tarball_path = self.build_logs_dir + ".tgz"
        tarball = tarfile.open(tarball_path, "w:gz")
        tarball.add(self.build_logs_dir)
        tarball.close()
        return tarball_path

    def start(self):
        self.get_source()
        ret = self.compile()
        if ret:
            pass
            self.mail_on_error(ret)
        if not self.package():
            print "Packaging failed!"
            return
        self.deploy()
        self.mail_on_success()

    def clear(self):
        if self.log_fp:
            self.log_fp.close()


def main():
    g = GenieBuilder()
    try:
        g.start()
    finally:
        g.clear()


if __name__ == '__main__':
    main()