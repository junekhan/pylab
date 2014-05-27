# -*- coding: UTF-8 -*-
__author__ = 'jun.han'

import os
import sys
import ConfigParser
import time
import selenium
import codecs
import ctypes
from win32api import MessageBox
from selenium import webdriver
from urlparse import urlparse


def click_until_success(clickable, time_to_wait_after_click):
    """ retry until page fully loaded, this is fundamental """
    while True:
        try:
            clickable.click()
            break
        except selenium.common.exceptions.TimeoutException:
            print 'Timeout on page loading'
    time.sleep(time_to_wait_after_click)


def check_connection(browser):
    panels = wrapped_find(browser.find_elements_by_xpath, "//div[@class='pane']")
    if panels[0].is_displayed():
        page = panels[0].find_element_by_xpath(".//iframe")
    else:
        page = panels[1].find_element_by_xpath(".//iframe")
    browser.switch_to.frame(page)
    browser.find_element_by_id('main-frame-error')


def click_and_check_failure(browser, clickable, time_to_wait_after_click):
    """ if connection loses, the program will retry until recovery
    """
    while True:
        try:
            browser.switch_to.default_content()
            click_until_success(clickable, time_to_wait_after_click)
            check_connection(browser)
            print 'the page is temporarily unavailable. retry in 30 seconds'
            time.sleep(30)
        except selenium.common.exceptions.NoSuchElementException:
            break

    browser.switch_to.default_content()


def click_and_wait(browser, clickable, time_to_wait_after_click):
    """  when using js to load target page, there are temporary pages in transition.
         we should wait for the page finally being loaded.
         here, we don't switch back to the default page, for the following addressing the form frame
    """
    need_click = True
    while True:
        try:
            if need_click:
                browser.switch_to.default_content()
                click_until_success(clickable, time_to_wait_after_click)
                form_frame = wrapped_find(browser.find_element_by_id, "formframe")
                browser.switch_to.frame(form_frame)
            browser.find_element_by_id('main-frame-error')
            print 'the page is temporarily unavailable. retry in 30 seconds'
            need_click = True
            time.sleep(30)
            continue
        except selenium.common.exceptions.NoSuchElementException:
            need_click = False

        try:
            browser.find_element_by_xpath("//script[@src='funcs.js' or @src='/funcs.js']")
            break
        except selenium.common.exceptions.NoSuchElementException:
            time.sleep(time_to_wait_after_click)

def wrapped_find(findmethod, arg, lineno = 0):
    """ retry when encountering with unavailable DOM element """
    while True:
        try:
            ret = findmethod(arg)
            break
        except selenium.common.exceptions.StaleElementReferenceException as e:
            print 'StaleElementReferenceException Raised! args: %s[%d]' % (arg, lineno)
        except Exception as e:
            raise e

    return ret

def close_other_wintabs(browser, handle_to_reserve):
    for each_handle in browser.window_handles:
        if each_handle != handle_to_reserve:
            browser.switch_to.window(each_handle)
            browser.close()
    browser.switch_to.window(handle_to_reserve)


def disk_free_space_detect(folder):
    """ get disk free space """
    free_bytes = ctypes.c_ulonglong(0)
    ctypes.windll.kernel32.GetDiskFreeSpaceExW(ctypes.c_wchar_p(folder), None, None, ctypes.pointer(free_bytes))
    print free_bytes.value/1024/1024
    if free_bytes.value/1024/1024 < 1024:
        MessageBox(0, u"截图路径所在分区空间不足1G!请在释放空间后按确定继续", 'Warning')

def hint():
    hintmsg = u'''
    1.测试过程中请保持浏览器最大化,并在所有窗口之前!
    2.请不要在本机或者其它机器打开测试路由的页面以影响测试结果。
    3.请不要在测试机上进行其它操作。
    单击确定开始测试。
    '''
    MessageBox(0, hintmsg, u'提示')


def get_encoding(cfgFilename):
    """ in case of unintentional addition of BOM """
    encoding = None
    if os.path.isfile(cfgFilename):
        fp = file(cfgFilename,'rb')
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


class AutoTest(object):
    def start(self):
        hint()
        config = ConfigParser.ConfigParser()
        config_file_name = '.\\autotest.ini'
        try:
            encoding = get_encoding(config_file_name)
            config.readfp(codecs.open(config_file_name, "r", encoding))
            self.website = config.get('base', 'homepage')
            if not self.website.endswith('/'):
                self.website += '/'
            self.save_path = config.get('base', 'screenshotpath')
            self.time_to_wait_after_click = int(config.get('base', 'TimeToWaitAfterClick'))
            self.time_to_wait_after_lang_switch = int(config.get('base', 'TimeToWaitAfterLangSwitch'))
            self.browser = webdriver.Chrome()
        except (ConfigParser.NoOptionError, ConfigParser.NoSectionError) as e:
            print "[Error]:%s" % e
            MessageBox(0, e.message, 'Error')
            quit()
        except selenium.common.exceptions.WebDriverException as e:
            ErrMsg = 'chromedriver.exe or chrome.exe is not available! Please check it out. '
            MessageBox(0, ErrMsg, 'Error')
            quit()

        self.save_path = self.save_path.replace('\\', '\\\\')
        if not os.path.isdir(self.save_path):
            MessageBox(0, u"截图保存路径不可用!", 'Error')
            quit()

        disk_free_space_detect(self.save_path)

        self.timestamp = time.strftime('%Y%m%d%H%M%S', time.localtime())

        self.browser.set_window_position(2500, 10)
        self.browser.maximize_window()
        self.browser.get(self.website)

        #for R1000
        try:
            time.sleep(self.time_to_wait_after_click)
            self.browser.switch_to.alert.dismiss()
        except selenium.common.exceptions.NoAlertPresentException:
            pass

        iframes1 = wrapped_find(self.browser.find_elements_by_id, "page")
        iframes2 = wrapped_find(self.browser.find_elements_by_id, "topframe")

        if len(iframes1) == 1:
            self.branch1()
        elif len(iframes2) == 1:
            self.branch2(iframes2[0])
        else:
            MessageBox(0, u"错误的页面", 'Error')
            self.browser.close()
            return None

        MessageBox(0, u"测试完成!", 'Info')
        self.browser.quit()

    def branch1(self):
        """ Modules:NetGear R7000 R3400 R4000 R6300
        """
        try:
            element = self.browser.find_element_by_name('srptlang')
        except Exception as e:
            MessageBox(0, u"错误的页面", 'Error')
            self.browser.close()
            raise e

        list_lang = element.get_attribute('value').split(' ')

        first_round = True

        for index_lang in range(0, len(list_lang)):
            #switch language
            each_lang = list_lang[index_lang]
            print each_lang
            disk_free_space_detect(self.save_path)
            next_option = wrapped_find(self.browser.find_element_by_xpath, "//option[@value='%s']" % each_lang)
            if not next_option.is_selected():
                next_option.click()
                time.sleep(5)
                while True:
                    try:
                        self.browser.switch_to.alert.accept()
                        break
                    except selenium.common.exceptions.NoAlertPresentException:
                        time.sleep(self.time_to_wait_after_click)
                    except selenium.common.exceptions.WebDriverException:
                        break

                #for R1000v3
                time.sleep(2)
                try:
                    self.browser.switch_to.alert.accept()
                except selenium.common.exceptions.NoAlertPresentException:
                    pass

                if first_round:
                    time.sleep(self.time_to_wait_after_lang_switch)  #wait for refreshing
                    first_round = False
                while True:
                    advance_panel = wrapped_find(self.browser.find_element_by_xpath, "//div[@class='pane'][2]")
                    if not advance_panel.is_displayed():
                        break
                    time.sleep(self.time_to_wait_after_click)

            self.browser.switch_to.default_content()
            advance_tab = wrapped_find(self.browser.find_element_by_id, 'AdvanceTab')

            current_path = '%s\\\\%s\\\\%s\\\\base' % (self.save_path, self.timestamp, each_lang)
            if not os.path.exists(current_path):
                os.makedirs(current_path)
            #basic menu routine
            basic_menu = wrapped_find(self.browser.find_element_by_xpath, "//div[@class='basic-menu']")
            basic_menu_divs = wrapped_find(basic_menu.find_elements_by_xpath, ".//div")
            for each in basic_menu_divs:
                anchor = wrapped_find(each.find_element_by_xpath, "a", sys._getframe().f_lineno)
                href = anchor.get_attribute('href')
                if href.startswith(self.website):
                    click_and_check_failure(self.browser, each, self.time_to_wait_after_click)
                    filename = urlparse(href).path[1:]
                    self.browser.get_screenshot_as_file('%s\\\\%s.png' % (current_path, filename))

            current_path = '%s\\\\%s\\\\%s\\\\advance' % (self.save_path, self.timestamp, each_lang)
            if not os.path.exists(current_path):
                os.makedirs(current_path)
            #advance menu routine
            advance_panel = wrapped_find(self.browser.find_element_by_xpath, "//div[@class='pane'][2]")
            advance_panel_list = wrapped_find(advance_panel.find_elements_by_xpath, ".//li")
            if not advance_panel.is_displayed():
                advance_tab.click()
                time.sleep(self.time_to_wait_after_click)
            for each in advance_panel_list:
                try:
                    anchor = wrapped_find(each.find_element_by_xpath, "a", sys._getframe().f_lineno)
                except selenium.common.exceptions.NoSuchElementException as e:
                    #non-existence is acceptable
                    continue

                href = anchor.get_attribute('href')
                #print href
                if href.startswith(self.website) and not href.endswith('#'):
                    click_and_check_failure(self.browser, each, self.time_to_wait_after_click)

                    #switch to subpage
                    sub_page = wrapped_find(self.browser.find_element_by_id, 'page2')
                    self.browser.switch_to.frame(sub_page)
                    sub_page_panel_list = wrapped_find(self.browser.find_elements_by_xpath, "//li")
                    sub_page_saved = False
                    sub_index = 0
                    for subeach in sub_page_panel_list:
                        try:
                            subanchor = wrapped_find(subeach.find_element_by_xpath, "a", sys._getframe().f_lineno)
                            sub_page_saved = True
                        except selenium.common.exceptions.NoSuchElementException as e:
                            #non-existence is acceptable
                            continue

                        sub_href = subanchor.get_attribute('href')

                        if sub_href.startswith(self.website):
                            click_and_check_failure(self.browser, subeach, self.time_to_wait_after_click)
                            addr_items = urlparse(sub_href)
                            sub_file_name = addr_items.path[1:]
                            if addr_items.fragment != "":
                                sub_file_name = sub_file_name + '#' + addr_items.fragment
                            elif sub_href.endswith('#'):
                                sub_file_name = sub_file_name + '#' + str(sub_index)
                                sub_index += 1

                            self.browser.get_screenshot_as_file('%s\\\\%s.png' % (current_path, sub_file_name))

                    #switch backward
                    self.browser.switch_to.default_content()
                    #otherwise the default page will be saved twice
                    if sub_page_saved is False:
                        addr_items = urlparse(href)
                        filename = addr_items.path[1:]
                        if addr_items.fragment != "":
                            filename = filename + '#' + addr_items.fragment
                        self.browser.get_screenshot_as_file('%s\\\\%s.png' % (current_path, filename))

                #unfold menu
                elif anchor.get_attribute('href').endswith('#'):
                    each.click()
                    time.sleep(1)

    def branch2(self, iframe):
        """ Modules: NetGear R4700
        """
        print 'branch 2'
        #switch to top
        self.browser.switch_to.frame(iframe)
        options = self.browser.find_elements_by_xpath("//option")
        list_lang = list()
        for each in options:
            list_lang.append(each.get_attribute('value'))

        local_win_handle = self.browser.current_window_handle
        for eachLang in list_lang:
            #switch language

            # print eachLang
            # if eachLang != 'Russian':
            #     continue
            disk_free_space_detect(self.save_path)

            self.browser.switch_to.default_content()
            top_frame = wrapped_find(self.browser.find_element_by_id, "topframe")
            form_frame = wrapped_find(self.browser.find_element_by_id, "formframe")
            self.browser.switch_to.frame(top_frame)

            next_option = wrapped_find(self.browser.find_element_by_xpath, "//option[@value='%s']" % eachLang)
            next_option.click()
            try:
                self.browser.switch_to.default_content()
                self.browser.switch_to.frame(form_frame)
                self.browser.find_element_by_xpath("//input[@name='yes']").click()
            except Exception as e:
                pass
            finally:
                self.browser.switch_to.default_content()

            time.sleep(self.time_to_wait_after_lang_switch)  #wait for refreshing

            top_frame = wrapped_find(self.browser.find_element_by_id, "topframe")
            self.browser.switch_to.frame(top_frame)

            advance_tab = wrapped_find(self.browser.find_element_by_id, 'advanced_label')
            if advance_tab.get_attribute('class').startswith('label_click'):
                basic_tab = wrapped_find(self.browser.find_element_by_id, 'basic_label')
                click_until_success(basic_tab, self.time_to_wait_after_click)
                top_frame = wrapped_find(self.browser.find_element_by_id, "topframe")
                self.browser.switch_to.frame(top_frame)
                advance_tab = wrapped_find(self.browser.find_element_by_id, 'advanced_label')

            #switch back
            self.browser.switch_to.default_content()
            #basic_menu_divs = wrapped_find(self.browser.find_elements_by_xpath, "//div[@class='basic_button']")
            basic_menu_divs = wrapped_find(self.browser.find_elements_by_xpath, "//div[@onclick]")

            current_path = '%s\\\\%s\\\\%s\\\\base' % (self.save_path, self.timestamp, eachLang)
            if not os.path.exists(current_path):
                os.makedirs(current_path)

            #basic menu routine
            for each_div in basic_menu_divs:
                do_not_capture = False
                #for R6050
                if each_div.get_attribute('style').startswith('display: none'):
                    continue

                click_and_wait(self.browser, each_div, self.time_to_wait_after_click)
                if len(self.browser.window_handles) != 1:
                    close_other_wintabs(self.browser, local_win_handle)
                    do_not_capture = True

                if not do_not_capture:
                    filename = urlparse(self.browser.current_url).path[1:]
                    self.browser.get_screenshot_as_file('%s\\\\%s.png' % (current_path, filename))
                self.browser.switch_to.default_content()

            #advance menu routine
            current_path = '%s\\\\%s\\\\%s\\\\advance' % (self.save_path, self.timestamp, eachLang)
            if not os.path.exists(current_path):
                os.makedirs(current_path)
            self.browser.switch_to.default_content()
            top_frame = wrapped_find(self.browser.find_element_by_id, "topframe")
            self.browser.switch_to.frame(top_frame)
            advance_tab.click()
            self.browser.switch_to.default_content()
            advance_menu_divs = wrapped_find(self.browser.find_elements_by_xpath,
                                             "//div[@onclick]")
            dls = self.browser.find_elements_by_xpath("//dl")
            index_dl = 0
            for index_adv in range(0, len(advance_menu_divs)):
                do_not_capture = False

                #for R6050. when the 'home' button is clicked, it causes the whole page refreshing, which leads all the
                #elements unavailable that are retrieved previously
                each = advance_menu_divs[index_adv]
                try:
                    each_class = each.get_attribute('class')
                except selenium.common.exceptions.StaleElementReferenceException as e:
                    advance_menu_divs = wrapped_find(self.browser.find_elements_by_xpath,
                                                     "//div[@onclick]")
                    dls = self.browser.find_elements_by_xpath("//dl")
                    each = advance_menu_divs[index_adv]
                #for R6050
                if each.get_attribute('style').startswith('display: none'):
                    continue

                if each_class.startswith('advanced_white_close_button'):
                    sub_dts = dls[index_dl].find_elements_by_xpath(".//dt")
                    index_dl += 1
                    sub_dts = [x for x in sub_dts if not x.get_attribute('style').startswith('display: none')]
                    each.click()
                    while True:
                        if sub_dts[0].is_displayed():
                            break
                        print 'element is not displayed'
                        time.sleep(self.time_to_wait_after_click)
                    for each_dts in sub_dts:
                        do_not_capture = False
                        #for R6050
                        if each_dts.get_attribute('style').startswith('display: none'):
                            continue

                        anchor = wrapped_find(each_dts.find_element_by_xpath, './/a')
                        click_and_wait(self.browser, anchor, self.time_to_wait_after_click)
                        if len(self.browser.window_handles) != 1:
                            close_other_wintabs(self.browser, local_win_handle)
                            do_not_capture = True

                        if not do_not_capture:
                            filename = urlparse(self.browser.current_url).path[1:]
                            self.browser.get_screenshot_as_file('%s\\\\%s.png' % (current_path, filename))
                        self.browser.switch_to.default_content()
                else:
                    click_and_wait(self.browser, each, self.time_to_wait_after_click)
                    if len(self.browser.window_handles) != 1:
                        close_other_wintabs(self.browser, local_win_handle)
                        do_not_capture = True

                    if not do_not_capture:
                        filename = urlparse(self.browser.current_url).path[1:]
                        self.browser.get_screenshot_as_file('%s\\\\%s.png' % (current_path, filename))
                    self.browser.switch_to.default_content()


def main():
    autotest = AutoTest()
    autotest.start()

if __name__ == '__main__':
    main()

