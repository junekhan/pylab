__author__ = 'jun.han'

import os
import sys
import ConfigParser
import codecs
import time
import shutil
import re
from win32api import MessageBox
from win32com.client import Dispatch


def get_encoding(cfg_filename):
    """ in case of unintentional addition of BOM """
    encoding = None
    if os.path.isfile(cfg_filename):
        fp = file(cfg_filename, 'rb')
        header = fp.read(4)
        fp.close()
        encodings = [(codecs.BOM_UTF32, 'utf-32-sig'),
                    (codecs.BOM_UTF16, 'utf-16-sig'),
                    (codecs.BOM_UTF8, 'utf-8-sig')]

        for h,e in encodings:
            if header.find(h) == 0:
                encoding = e
                break

    return encoding


class AutoReport(object):
    def __init__(self):
        self.excel_app = Dispatch("Excel.Application")

        config_file_name = '.\\autoreport.ini'
        self.config = ConfigParser.ConfigParser()
        encoding = get_encoding(config_file_name)
        self.config.readfp(codecs.open(config_file_name, "r", encoding))

        self.xls_boilerplate_path = self.config.get('base', 'boilerplate')
        self.timestamp = time.strftime('%Y%m%d', time.localtime())
        self.report_filename = ''
        self.report_file = None
        self.work_sheet = None
        self.first_used_row_index = 0
        self.keyword_list = []
        self.logfile_name = sys.argv[1]
        self.logfile = None
        self.log_snippets = []

    def start(self):
        self.report_filename = '%s_%s.%s' % ('.'.join(self.logfile_name.split('.')[0:-1]), self.timestamp,
                                   self.xls_boilerplate_path.split('.')[-1])

        if os.path.exists(self.report_filename):
            os.rename(self.report_filename, (self.report_filename + '.bak'))
        shutil.copyfile(self.xls_boilerplate_path, self.report_filename)

        self.get_keyword_list()
        self.get_log_snippets()

        patterns = []
        for each_kw in self.keyword_list:
            patterns.append(re.compile(u'%s\s+(\d+) kB' % each_kw))

        index = self.first_used_row_index
        for i in range(1, len(self.log_snippets)):
            if self.work_sheet.Cells(index, 1).Value is None:
                break
            for each_pattern in patterns:
                ret = each_pattern.search(self.log_snippets[i])
                if ret is not None:
                    self.work_sheet.Cells(index, 2).Value = ret.group(1)

                index += 1

        self.report_file.Save()


    def get_keyword_list(self):

        self.report_file = self.excel_app.Workbooks.Open((os.path.split(os.path.abspath(__file__))[0]
                                                         + '\\' + self.report_filename))
        #self.excel_app.Visible = True
        self.work_sheet = self.report_file.Worksheets[0]
        index = 1
        while True:
            value = self.work_sheet.Cells(index, 1).Value
            if value is not None:
                if value in self.keyword_list:
                    break
                self.keyword_list.append(value)
                if self.first_used_row_index == 0:
                    self.first_used_row_index = index
            index += 1

    def get_log_snippets(self):
        if os.path.exists(self.logfile_name):
            self.logfile = open(self.logfile_name, 'r')
            content = self.logfile.read()
            self.log_snippets = re.findall(u"(MemTotal:[\s\S]*?(?=MemTotal:)|MemTotal:[\s\S]+)", content)

            # snippets1 = content.split("cat /proc/meminfo")
            # snippets2 = content.split("PID  Uid        VSZ Stat Command")
            # self.log_snippets = snippets1 if len(snippets1) > len(snippets2) else snippets2
            # if re.search("cat /proc/meminfo", content):
            #     self.log_snippets = content.split("cat /proc/meminfo")
            # else:
            #     self.log_snippets = content.split("PID  Uid        VSZ Stat Command")
            self.logfile.close()
            self.logfile = None

    def clear(self):
        if self.excel_app:
            if self.report_file:
                self.report_file.Close()
            self.excel_app.Quit()

        if self.logfile:
            self.logfile.close()

def main():
    try:
        autoreport = AutoReport()
        autoreport.start()
    except BaseException as e:
        print e.message
        #MessageBox(0, str(e.message), u'Runtime Error')
    finally:
        autoreport.clear()


if __name__ == '__main__':
    main()
