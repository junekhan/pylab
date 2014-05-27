__author__ = 'jun.han'

import os
import codecs

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