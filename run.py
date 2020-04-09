#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
if sys.version_info < (3,0):
    exit('[Failed] python 3.x required')
import os
import shutil
import re
from time import sleep
import datetime
import collections
#import config



'''
script_dir=os.path.split(os.path.realpath(__file__))[0]+'/'

data_dir="%s%s"%(script_dir,config.storage_subdir)
backup_dir="%s%s"%(script_dir,config.backup_subdir)

'''

def infer_type(data,dtype={}):
    # data 为待推荐数据，字典类型
    # dtype为推荐结果字典，key为字段名，value为列表。  value 列表元素如下
    # 非空值个数， 字符串最大长度,  正int型数目,  日期型个数
    # 示例 {'PMID':[100,20,90,0], ...}
    #   有点复杂，先只实现字符串及int两个类型好了
    # 非字符串类型直接忽略，所以字典型要单独推断
    for fn in data:
        if fn not in dtype:
            dtype[fn]=[0,0,0,0]
        if isinstance(data[fn],str):
            if data[fn]!='': dtype[fn][0] += 1
            length=len(data[fn])
            if length > dtype[fn][1]: dtype[fn][1]=length
            if re.compile('^[\d]+$').match(data[fn]):
                dtype[fn][2] += 1
    return dtype




link=None           # mysql connection link
cursor=None    # Cursor for cursor_publish, cursor_author
col_p=['PMID','OWN','STAT','LR','IS_Linking','IS_Electronic','IS_Print','VI'
    ,'DP','TI','PG','LID_pii','LID_doi','AB','CI','LA','PT','DEP'
    ,'PL','TA','JT','JID','OTO','OT','EDAT','MHDA','CRDT','PHST_accepted'
    ,'PHST_aheadofprint','PHST_entrez','PHST_medline','PHST_pmc-release'
    ,'PHST_pubmed','PHST_received','PHST_retracted','PHST_revised','AID_pii'
    ,'AID_doi','AID_bookaccession','PST','SO','AUID','GR','IP','EFR','SI'
    ,'PMC','MID','IR','FIR','CIN','EIN','CON','SB','MH','RN','ROF','TT'
    ,'COIS','PMCR','UOF']
col_a=['PMID','FAU','AU','1st','idx','AD1','AD2']
# pubmed_paper 默认值集合（字典），其中有int型单独置0，在插入时将真实值update到该字典中
def_p=dict([(it,'') for it in col_p ])
def_p['LR']=0
def_p['DEP']=0
# 字符串型字段长度，在表结构中读取；直接修改表中字段长度而不改程序，毕竟修正一大堆字段的截断长度太繁琐
col_size_p=col_size_a={}
col_exceeded_count_p=col_exceeded_count_a={}

sql_p="INSERT INTO `pubmed_paper`(%s) VALUES (%s)"%(
        '`' + '`, `'.join(col_p) + '`',
        '%(' + ')s, %('.join(col_p) + ')s' )

sql_a="INSERT INTO `pubmed_author`(%s) VALUES (%s)"%(
        '`' + '`, `'.join(col_a) + '`',
        '%(' + ')s, %('.join(col_a) + ')s' )

import pymysql
def save_buff(buff):
    global link,cursor,col_p,col_a,sql_p,sql_a,col_size_p,col_size_a
    if link==None:
        link=pymysql.connect(host='127.0.0.1', user='root', password='bioon.com'
            , db='transfer_tmp', charset='utf8'
            ,cursorclass=pymysql.cursors.DictCursor)
        cursor=link.cursor()
        cursor.execute("SELECT COLUMN_NAME as `name`,CHARACTER_MAXIMUM_LENGTH as `size` \
            FROM `information_schema`.`COLUMNS` \
            WHERE `TABLE_NAME`='pubmed_paper' AND `TABLE_SCHEMA`='transfer_tmp' \
            AND DATA_TYPE='varchar'")
        col_size_p=dict( [(res['name'],res['size']) for res in cursor.fetchall()] )
        cursor.execute("SELECT COLUMN_NAME as `name`,CHARACTER_MAXIMUM_LENGTH as `size` \
            FROM `information_schema`.`COLUMNS` \
            WHERE `TABLE_NAME`='pubmed_author' AND `TABLE_SCHEMA`='transfer_tmp' \
            AND DATA_TYPE='varchar'")
        col_size_a=dict( [(res['name'],res['size']) for res in cursor.fetchall()] )

    # 拆分值
    if 'PMID' not in buff or not buff['PMID']:
        print("[warning] bad buff, 'PMID' not exists, skiped.")
        return
    # 按 col_size_p 检查buff中值长度，做截断及计数
    for it in col_size_p:
        if it not in buff: continue
        length=len(buff[it])
        if length > col_size_p[it]:
            buff[it]=buff[it][:col_size_p[it]]
            if it in col_exceeded_count_p:
                col_exceeded_count_p[it]+=1
            else:
                col_exceeded_count_p[it] =1
    paper=def_p.copy()
    paper.update(buff)
    insert_error=False
    try:
        cursor.execute(sql_p,paper)
    except pymysql.err.IntegrityError as e:
        insert_error=True
        if e.args[0]==1062:
            print('Duplicate entry, skiped.   PMID: %s'%buff['PMID'])
        else:
            print(e)
            print(buff)
    #except:
    #    print(buff)
    
    if not insert_error and 'AUTHORS' in buff:
        for it in buff['AUTHORS']:
            buff['AUTHORS'][it]['PMID']=buff['PMID']
            cursor.execute(sql_a,buff['AUTHORS'][it])
    link.commit()
    return



def dump_buff(buff):
    #return
    if not [ it for it in buff['AUTHORS'] if buff['AUTHORS'][it]['AD2']!='' ]:return
    print('\n***** saving buff....')
    print('---- buff ---------------------\n')
    '''
    for key in ['PMID','OWN','STAT','LR','IS','VI','DP','TI','PG','LID','AB','CI','AUTHORS','FAU','AU','AD','LA','PT','DEP','PL','TA','JT','JID','OTO','OT','EDAT','MHDA','CRDT','PHST','AID','PST','SO','AUID','GR','IP','COI','EFR','SI','PMC','MID','IR','FIR','CIN','EIN','CON','DCO','SB','MH','RN','ROF','TT','UOF']:
        if key in buff:
            if isinstance(buff[key], dict):
                print('  %s:'%key )
                for it in buff[key]:
                    print('    %s: %s'%(it,buff[key][it]))
            else:
                print('  %s: %s'%(key,buff[key] if len(buff[key]) < 80 else buff[key][:80]+'...'))
    '''
    for key in buff:
        if isinstance(buff[key], dict):
            print('  %s:'%key )
            for it in buff[key]:
                print('    %s: %s'%(it,buff[key][it]))
        else:
            print('  %s: %s'%(key,buff[key] if len(buff[key]) < 80 else buff[key][:80]+'...'))
    print('\n-------------------\n')

def fix_buff(buff):
    # 在持久化前修正数据，主要是作者信息，多个地址优选、补省略的地址等
    if 'AUTHORS' not in buff: return buff
    del buff['_curr_author']
    for fname in buff['AUTHORS']:
        addrs=buff['AUTHORS'][fname]['AD']
        addrs=[ it for it in addrs if 'China' in it and 'Hospital' in it] \
             +[ it for it in addrs if 'China' in it and 'Hospital' not in it] \
             +[ it for it in addrs if 'China' not in it and 'Hospital' not in it] \
             +['','']
        del buff['AUTHORS'][fname]['AD']
        buff['AUTHORS'][fname]['AD1']=addrs[0]
        buff['AUTHORS'][fname]['AD2']=addrs[1]
    # 按次序idx与姓名fname的字典 {idx1:fname1,idx2:fname2,...}, 按idx排序后遍历，补充省略的地址
    ad_1=ad_2=''
    mp = { buff['AUTHORS'][it]['idx']:it for it in buff['AUTHORS'] }
    for i in sorted(mp):
        if buff['AUTHORS'][mp[i]]['AD1']:
            ad_1=buff['AUTHORS'][mp[i]]['AD1']
            ad_2=buff['AUTHORS'][mp[i]]['AD2']
        elif ad_1:
            buff['AUTHORS'][mp[i]]['AD1']=ad_1
            buff['AUTHORS'][mp[i]]['AD2']=ad_2
    return buff

# 合并一个key-value对到buff中，有多种情况：
#   一对一，如 PMID
#   一对多，如 OT
#   一对多个组合的一组，如 FAU,AU,AD，这里的AD还有多地址的，相当多10%以上，首选中国的地址
#   重新拆解组合，如 IS 拆出 Electronic, Print, Linking 等几种 issn号
def merge_kv(key,value,buff):
    if key in ['DCOM','RIN','','ECF','CTDT','IRAD','FED','ED','CDAT','ISBN'
                ,'DA','PB','BTI','DRDT','CP','','CN','GN','RF','FPS']:
        # 忽略的key
        return buff
    if key in ['PMID','OWN','STAT','LR','DP','TI','PL','TA'
                ,'JT','JID','EDAT','MHDA','CRDT','PST','SO','AB','DEP'
                ,'OTO','GR','PG','VI','AUID','IP','MH','CI','PMC','COI'
                ,'IR','FIR','RN','SB','DCO','SI','EFR','CON','MID'
                ,'EIN','CIN','ROF','TT','UOF'
                ,'COIS','PMCR']:
        # TODO  从'OTO'开始往下的字段过于稀少，如无价值，视情况忽略掉
        buff[key]=value
    elif key == 'LA' and 'LA' not in buff:
        # 如有多个，以首次为准； 主要是 'LA' 语言一项，大概 0.1% 的多语言条目
        buff[key]=value
    elif key in ['PT','OT']:
        # PT,OT  直接使用拼接在一起好了
        if key in buff:
            buff[key]+=' | '+value
        else:
            buff[key] = value
    elif key in ['IS','LID','AID','PHST']:
        # 各key有不同的子key
        sub_keys={
            'IS'  : ['Electronic','Linking','Print'],
            'LID' : ['pii','doi'],
            'AID' : ['pii','doi'],
            'PHST': ['received','revised','accepted','entrez','pubmed','medline','pmc-release'],
            }[key]
        sub_keys_skip={
            'IS'  : [],
            'LID' : [],
            'AID' : ['bookaccession',],
            'PHST': ['aheadofprint','retracted'],
            }[key]

        # 拆分成多个，分别一对一，IS 值为圆括号，其它为方括号
        if key=='IS':
            needle_a, needle_b=' (', ')'
        else:
            needle_a, needle_b=' [', ']'
        pos_a=value.find(needle_a)
        pos_b=value.find(needle_b)
        if pos_a < 0 or pos_b < 0 :
            print('[warning] PMID %s: needles %s,%s for %s not found in \n %s'%(
                buff['PMID'],needle_a,needle_b,key,value) )
        else:
            sk=value[pos_a+2:pos_b]
            if sk not in sub_keys and sk not in sub_keys_skip:
                print('[warning] PMID %s: unknown sub_key %s in %s, expect %s'%(
                    buff['PMID'] if 'PMID' in buff else '[NO-PMID]',
                    sk,key,sub_keys ))
            else:
                buff['%s_%s'%(key,sk)]=value[:pos_a]
    elif key in ['FAU','AU','AD']:
        # 作者，对连续的多个重新组合，得到一系列以全名为键的字典，整体以'AUTHORS'为键存入buff
        # {
        #   'Zhang, San': {'FAU':'Zhang, San', 'AU':'Zhang, S', 'AD':'...', '1st':'Y'},
        #   'Li, Si':     {'FAU':'Li, Si',     'AU':'Li, S',    'AD':'...', '1st':'N'},
        # }
        # 其中 'AD' 是列表，所有地址，拟在存储时选择其中两个存储，如果超过两个的话
        #   通过内部标识 _curr_author 标定当前处理的作者，填充到
        # 另外，还有 key 为 'CN' 的，为以单位名义的作者，Corporate Author，暂时忽略，量极少，在目前程序结构里不便拆分
        if key=='FAU':
            if 'AUTHORS' not in buff:
                buff['AUTHORS']={value:{'FAU':value,'AU':'','AD':[], '1st':'Y','idx':0}}
            else:
                buff['AUTHORS'][value]={'FAU':value,'AU':'','AD':[], '1st':'N','idx':len(buff['AUTHORS'])}
            buff['_curr_author']=value
        elif '_curr_author' not in buff:
            print('[warning] _curr_author not set when parsing Authors, PMID: %s'%(
                buff['PMID'] if 'PMID' in buff else '<unset PMID>'))
        elif key=='AU':
            buff['AUTHORS'][buff['_curr_author']]['AU']=value if buff['_curr_author'] in buff['AUTHORS'] else ''
        elif key=='AD' and buff['_curr_author'] in buff['AUTHORS']:
            buff['AUTHORS'][buff['_curr_author']]['AD'].append(value)
    else:
        print('[Alert] skiped unknown field: %s'%key)
    return buff



if __name__ == '__main__':
    filename='data/pubmed_result_concated.txt'
    #filename='data/pubmed_result_tiny.txt'
    f=open(filename,'r',encoding='utf-8')
    i=0
    buff={}     # 格式化的每条行数据集
    dtype={}   # 每条数据集内部字段计数，及计算推断长度、推断类型，参看 infer_buff() 中定义
    dtype_au={}
    key=value=''
    while True:
        line=f.readline()
        if line==None:
            break
        i+=1;
        #if i < 1222: continue
        #if i > 1300: break
        if i % 100000==0: print('----- position: %s ------ '%format(i,','))
        # 保存解析到缓冲区的数据集
        if line=='':
            print('\nread EOF in %s'%filename)
            break
        elif line=='\n' and buff :
            buff=fix_buff(buff)
            # #### 下面的两个执行，1)推断字段 ，2)持久化
            # 实际使用时先跑一遍 1)推断字段，得到数据类型构造建表语句，然后执行 2)持久化存储
            # 0. 输出内容，算是调试
            #dump_buff(buff)

            '''
            # 1. 推断字段
            dtype=infer_type(buff,dtype)
            if 'AUTHORS' in buff:
                for it in buff['AUTHORS']:
                    dtype_au=infer_type(buff['AUTHORS'][it],dtype_au)

            '''
            # 2. 持久化存储
            save_buff(buff)
            

            # 清理缓冲区，为下一条MEDLINE数据行准备
            buff={}
        elif line[4:6]=='- ':
            # 归整上一条key-value值，然后缓冲下一个k-v对
            buff=merge_kv(key,value,buff)
            key=line[:4].strip()
            value=line[6:-1]
        elif line[:6]=='      ':
            value+=' '+line[6:-1]
        else:
            print('[warning] unexpected line:\n%s'%line)

    print('\n---------- Done, raw file line count %s -----'%format(i,','))
    for it in dtype:
        print('%s    : %s'%(it,dtype[it]))
    print('\n-------------------------\n')
    for it in dtype_au:
        print('%s    : %s'%(it,dtype_au[it]))

    print('\n---- col_exceeded_count_p   %s ---------------------\n'%(len(col_exceeded_count_p)))
    for it in col_exceeded_count_p:
        print('  %s : %s'%(it,col_exceeded_count_p[it]))
    print('\n-------------------------\n')



'''
CREATE TABLE `pubmed_paper` (
  `PMID` int(11) NOT NULL DEFAULT '0',
  `OWN` varchar(3) DEFAULT NULL,
  `STAT` varchar(18) DEFAULT NULL,
  `LR` int(11) DEFAULT NULL,
  `IS_Linking` varchar(9) DEFAULT NULL,
  `IS_Electronic` varchar(9) DEFAULT NULL,
  `IS_Print` varchar(9) DEFAULT NULL,
  `VI` varchar(17) DEFAULT NULL,
  `DP` varchar(27) DEFAULT NULL,
  `TI` mediumtext,
  `PG` varchar(30) DEFAULT NULL,
  `LID_pii` varchar(70) DEFAULT NULL,
  `LID_doi` varchar(53) DEFAULT NULL,
  `AB` mediumtext,
  `CI` mediumtext,
  `LA` varchar(3) DEFAULT NULL,
  `PT` varchar(230) DEFAULT NULL,
  `DEP` int(11) DEFAULT NULL,
  `PL` varchar(25) DEFAULT NULL,
  `TA` varchar(59) DEFAULT NULL,
  `JT` varchar(239) DEFAULT NULL,
  `JID` varchar(9) DEFAULT NULL,
  `OTO` varchar(6) DEFAULT NULL,
  `OT` mediumtext,
  `EDAT` varchar(16) DEFAULT NULL,
  `MHDA` varchar(16) DEFAULT NULL,
  `CRDT` varchar(16) DEFAULT NULL,
  `PHST_accepted` varchar(16) DEFAULT NULL,
  `PHST_aheadofprint` varchar(16) DEFAULT NULL,
  `PHST_entrez` varchar(16) DEFAULT NULL,
  `PHST_medline` varchar(16) DEFAULT NULL,
  `PHST_pmc-release` varchar(16) DEFAULT NULL,
  `PHST_pubmed` varchar(16) DEFAULT NULL,
  `PHST_received` varchar(16) DEFAULT NULL,
  `PHST_retracted` varchar(16) DEFAULT NULL,
  `PHST_revised` varchar(16) DEFAULT NULL,
  `AID_pii` varchar(70) DEFAULT NULL,
  `AID_doi` varchar(53) DEFAULT NULL,
  `AID_bookaccession` varchar(9) DEFAULT NULL,
  `PST` varchar(12) DEFAULT NULL,
  `SO` varchar(140) DEFAULT NULL,
  `AUID` varchar(60) DEFAULT NULL,
  `GR` mediumtext,
  `IP` varchar(56) DEFAULT NULL,
  `EFR` varchar(245) DEFAULT NULL,
  `SI` varchar(56) DEFAULT NULL,
  `PMC` varchar(12) DEFAULT NULL,
  `MID` varchar(12) DEFAULT NULL,
  `IR` varchar(21) DEFAULT NULL,
  `FIR` varchar(30) DEFAULT NULL,
  `CIN` varchar(91) DEFAULT NULL,
  `EIN` mediumtext,
  `CON` varchar(90) DEFAULT NULL,
  `SB` varchar(3) DEFAULT NULL,
  `MH` varchar(107) DEFAULT NULL,
  `RN` varchar(140) DEFAULT NULL,
  `ROF` varchar(158) DEFAULT NULL,
  `TT` mediumtext,
  `COIS` mediumtext,
  `PMCR` varchar(16) DEFAULT NULL,
  `UOF` varchar(99) DEFAULT NULL,
  PRIMARY KEY (`PMID`)
) ENGINE=MyISAM DEFAULT CHARSET=utf8;

CREATE TABLE `pubmed_author` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `PMID` int(11) DEFAULT NULL,
  `FAU` varchar(108) DEFAULT NULL,
  `AU` varchar(92) DEFAULT NULL,
  `1st` varchar(1) DEFAULT NULL,
  `idx` int(11) DEFAULT NULL,
  `AD1` mediumtext,
  `AD2` mediumtext,
  PRIMARY KEY (`id`),
  KEY `PMID` (`PMID`)
) ENGINE=MyISAM DEFAULT CHARSET=utf8;
'''






