#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
if sys.version_info < (3,0):
    exit('[Failed] python 3.x required')
import os
import shutil
import glob
from time import sleep
import datetime
import collections
#import config



'''
script_dir=os.path.split(os.path.realpath(__file__))[0]+'/'

data_dir="%s%s"%(script_dir,config.storage_subdir)
backup_dir="%s%s"%(script_dir,config.backup_subdir)

'''





if __name__ == '__main__':
    filename='data/pubmed_result.txt'
    #filename='data/pubmed_result_tiny.txt'
    f=open(filename,'r',encoding='utf-8')
    '''
    # 提取所有标题列，并统计频次
    for i in range(100000000):
        line=f.readline()
        if line=='':
            break
        pos=line.find('-')
        if pos < 0 or pos > 6:
            continue
        fn=line[:pos-1].strip()
        if fn=='' :
            continue
        if fn not in fns:
            fns[fn]=1
        else:
            fns[fn]+=1
    for i in fns:
        print("%s : %s"%(i,fns[i]))
    '''

    fns=collections.OrderedDict()
    # 统计指定字段中所关心部分的频次
    dd={}
    dd['IS']={}
    dd['LID']={}
    dd['PHST']={}
    dd['AID']={}

    i=0
    while True:
        i+=1
        line=f.readline()
        if i % 100000==0: print('----- position: %s ------ '%format(i,','))
        #if i > 10000: break
        if line=='':
            break
        key=line[:4].strip()
        value=line[6:-1]

        if key=='': continue
        if key not in fns:
            fns[key]=1
        else:
            fns[key]+=1

        if key in ['IS','LID','AID','PHST']:
            # 拆分成多个，分别一对一，IS 值为圆括号，其它为方括号
            if key=='IS':
                needle_a, needle_b=' (', ')'
            else:
                needle_a, needle_b=' [', ']'
            pos_a=value.find(needle_a)
            pos_b=value.find(needle_b)
            if pos_a < 0 or pos_b < 0 :
                continue
            sk=value[pos_a+2:pos_b]
            if sk in dd[key]:
                dd[key][sk]+=1
            else:
                dd[key][sk] =1

    print('\n-------------\n')
    for i in fns:
        print("%s;%s"%(i,fns[i]))

    print('\n-------------\n')
    for k1 in dd:
        for k2 in dd[k1]:
            print('%s;%s;%s'%(k1,k2,dd[k1][k2]))

    print('\n%s done -------------\n'%filename)








