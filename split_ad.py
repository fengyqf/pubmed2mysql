#!/usr/bin/env python
# -*- coding: utf-8 -*-
  
import sys
if sys.version_info < (3,0):
    exit('[Failed] python 3.x required')
import os
import shutil
import re
from time import sleep
import pymysql
#import config


    
'''
script_dir=os.path.split(os.path.realpath(__file__))[0]+'/'

data_dir="%s%s"%(script_dir,config.storage_subdir)
backup_dir="%s%s"%(script_dir,config.backup_subdir)

'''



def parse_ad(ad):
    buff={'AD':'','depart':'','hosp':'','affiliated':'','addr':'','email':''}
    if not isinstance(ad,str) or not str:
        return buff
    buff['AD']=ad
    # 找 hosp, 所在的一段即为单位名称，
    #    然后检查其后一段是附属还是地址，其前为科室研究所部门
    ad_lower=ad.lower()
    # 几个位置标识：
    #   pos_0   'hosp' 所在一节的起始位置
    #   pos_1   'hosp' 的位置
    #   pos_2   连续的 'hosp' 节的结束位置
    #   pos_3   'univ'/'colle' 所在一节结束位置
    pos_0=pos_1=pos_2=pos_3=0
    pos_1=ad_lower.find('hosp')
    if pos_1 >= 0:
        pos_0=ad_lower[:pos_1].rfind(',')
        if pos_0 < 0:
            pos_0 = 0
        buff['depart']=ad[:pos_0]
        # 检查 pos_1 后面一段是否也是医院名称（多医院名），若是以后面一个为准
        pos_2=pos_x=pos_y=pos_1
        while True:
            pos_x=ad_lower.find(',',pos_x+1)    # 'hosp' 起的第n个逗号 ,
            pos_y=ad_lower.find(',',pos_x+1)    # 再往后的一个逗号
            if pos_x < 0:       # 'hosp' 后无逗号
                pos_2=len(ad_lower)
                break
            else:
                pos_2=pos_x
            if 'hosp' not in ad_lower[pos_x:pos_y]:
                # 无 'hosp'
                break
            else:
                pos_2=pos_y
        #pos_2=ad_lower.find(',',pos_1)
        if pos_2 < 0:
            pos_2=ad_lower.find(';',pos_1)
        if pos_2 > 0:
            buff['hosp']=ad[pos_0:pos_2]
        else:
            pos_2 = 0
    else:
        # 无hosp，检查univ/colle前是否有depart一节，在下面pos_3计算完成后执行
        pass

    pos_3=max(ad_lower.rfind('univ',pos_2),ad_lower.rfind('colle',pos_2))
    if pos_3 > 0:
        # 针对无hosp的ad，检查是否前面有depart一节
        if pos_1 < 0:
            pos_x=ad_lower[:pos_3].find('depart')
            if pos_x >= 0:
                # 从第一次出现univ/colle位置pos_y起，往前找逗号，即pos_0,pos_2
                pos_y=min(ad_lower.rfind('univ',pos_2),ad_lower.rfind('colle',pos_2))
                pos_0=pos_2=ad_lower[:pos_3].rfind(',')
                buff['depart']=ad[:pos_0]
        # 从'univ'/'colle'起的逗号或分号位置，作为最终的pos_3
        pos_x=ad_lower.find(',',pos_3)
        if pos_x < 0:
            pos_x=ad_lower.find(';',pos_3)
        if pos_x > 0:
            pos_3=max(pos_2,pos_x)
    else:
        pos_3=pos_2     # 无高校标识，以hosp结束位置为高校标识结束位置
    buff['affiliated']=ad[pos_2:pos_3]
    '''
    '''
    # pos_4 地址addr 结束位置
    if ad_lower[-5:] in ['china','hina.']:
        pos_4=-999
    else:
        pos_4=ad_lower.rfind('china.',pos_3)
        if pos_4 > 0:
            pos_4 += 6
        else:
            pos_4=ad_lower.find('. ',pos_3)
            if ad_lower[pos_4-2:pos_4]=='no':
                pos_4=ad_lower.find('. ',pos_4+1)
    if pos_4 < 0:
        pos_4=ad_lower.find(';',pos_2)
    if pos_4 < 0:
        m=re.findall(r"[\w\.-]+@[\w\.-]+\.\w{2,4}",ad_lower)
        if m:
            pos_4=ad_lower.find(m[0])
    if pos_4 > 0:
        buff['addr']=ad[pos_3:pos_4]
        buff['email']=ad[pos_4:]
    else:
        buff['addr']=ad[pos_3:]

    # hacking 若无univ，尝试在depart中提取
    if not buff['affiliated']:
        # 有逗号，以逗号拆分选带 univ/colle 的一节，略掉大写字母
        if ', ' in buff['depart'] and \
            ('niv' in buff['depart'] or 'olle' in buff['depart']):
            for it in buff['depart'].split(', '):
                if ('niv' in it or 'olle' in it) and 'epart' not in it:
                    buff['affiliated']=it
                    break
        else:
            # TODO 根据语义拆分字符串
            pass



    for it in buff:
        buff[it]=buff[it].strip('.,; ')
    if ':' in buff['email']:
        buff['email']=buff['email'][buff['email'].find(':')+1:].strip()
    return buff





def run():
    batch_size=1000     # 读取数据表每批大小

    link=pymysql.connect(host='127.0.0.1', user='root', password='bioon.com'
            , db='transfer_tmp', charset='utf8'
            ,cursorclass=pymysql.cursors.DictCursor)
    cursor=link.cursor()
    sql="SELECT min(id) as id_min,max(id) as id_max FROM pubmed_author"
    cursor.execute(sql)
    result=cursor.fetchone()
    id_min,id_max=result['id_min'],result['id_max']
    print('scan id range: (%s,%s)'%(id_min,id_max))
    for pos in range(id_min,id_max,batch_size):
        print('---- pos:%s      %.3f%%'%(pos,100.0*pos/(id_max - id_min )))
        sql="SELECT id,mk,AD1,AD2 FROM pubmed_author \
            WHERE id >= %s and id < %s"%(pos,pos+batch_size)
        cursor.execute(sql)
        sql="INSERT INTO pubmed_author_ad(id,n,AD,depart,hosp,affiliated,addr,email)\
            VALUES(%(id)s,%(n)s,%(AD)s,%(depart)s,%(hosp)s,%(affiliated)s,%(addr)s,%(email)s)"
        for row in cursor.fetchall():
            #if not row['AD1'] or row['mk']==0:
            #    continue
            pieces=parse_ad(row['AD1'])
            pieces['id']=row['id']
            pieces['n']=1
            cursor.execute(sql,pieces)
            
            if not row['AD2']:
                continue
            pieces=parse_ad(row['AD2'])
            pieces['id']=row['id']
            pieces['n']=2
            cursor.execute(sql,pieces)
        link.commit()
    link.close()

def testing():
    ad=[]
    '''
    '''
    ad.append("Department of Obstetrics and Gynecology, Peking University People's Hospital, Beijing 100044, China.")
    ad.append("Department of Hematology, The First Affiliated Hospital of Nanjing Medical University, Jiangsu Province Hospital, Nanjing, China.")
    ad.append("Shenzhen East-Lake Hospital, Children's Hospital, Shenzhen 518020, China.")
    ad.append("West China Hospital, Sichuan University, Chengdu 610041, China.")
    ad.append("Department of neurosurgery of Changhai hospital affiliated to the Second Military Medical University, Shanghai, China. Electronic address: chstroke@163.com.")
    ad.append("Department of Obstetrics and Gynecology, Peking University People's Hospital, Beijing 100044, China.")
    ad.append("Department of Surgical Oncology, Second Affiliated Hospital, Zhejiang University  College of Medicine, Hangzhou, Zhejiang 310009, PR China.")
    ad.append("Tumor Immunology and Gene Therapy Center, Eastern Hepatobiliary Hospital, Second  Military Medical University, 225 Changhai Road, Shanghai 200438, China.")
    ad.append("West China Hospital, Sichuan University, Chengdu 610041, China.")
    ad.append("Department of Surgery, The University of Hong Kong, Queen Mary Hospital, Pokfulam, Hong Kong, China.")
    ad.append("Department of Neurosurgery, Second Affiliated Hospital of Xi'an Jiaotong University College of Medicine, Xi'an 710004, China. shpinggg@126.com")
    ad.append("Department of Medical Oncology, Cancer Institute and Hospital, Chinese Academy of Medical Sciences, Beijing, China. xiaokzhang9@163.com.")
    ad.append("College of Engineering, Khalifa University of Science, Technology and Research, Abu Dhabi, UAE.")
    ad.append("Department of Informatics, Kings College London, London, WC2R 2LS, UK.")
    ad.append("1 Laboratories of Stem Cell Biology and Regenerative Medicine, Experimental Research Center and Neurological Disease Center, Beijing Friendship Hospital, Capital Medical University, Beijing, China.")
    ad.append("State Key Laboratory of Cellular Stress Biology, Innovation Center for Cell Signaling Network, School of Life Sciences, Xiamen University, Xiamen, Fujian 361102, China.")
    ad.append("Department of Cardiology, Affiliated Drum Tower Hospital, Nanjing University Medical School, Nanjing, China.")
    ad.append("School of Chemistry and Chemical Engineering, Southeast University, Nanjing, 211189, China; Qinzhou University, 12 Binhai Avenue, Qinzhou, Guangxi, China.")
    ad.append("Department of neurosurgery of Changhai hospital affiliated to the Second Military Medical University, Shanghai, China. Electronic address: chstroke@163.com.")
    ad.append("The Medical Science College of Sichuan Province, Sichuan Provincial Hospital, Chengdu 610072, China. lyf715@163.com")
    ad.append("Hospital of Metabolic Diseases, Tianjin Medical University, Tianjin 300070, China")
    ad.append("Department of Medical Oncology, Affiliated Cancer Hospital, Shantou University Medical College, Shantou, 515031, China")
    ad.append("Department of Medical Genetics and Medical Research, China Medical University Hospital, No. 2 Yuh-Der Road, Taichung, Taiwan, ROC. leiwan@mail.cmuh.org.tw")
    ad.append("Harbin Medical University, Harbin, China Department of Hematology, Radiology Branch, First Affiliated Hospital, Harbin Medical University")
    for it in ad:
        print('\n------------\n%s\n'%(it))
        pieces=parse_ad(it)
        del pieces['AD']
        print(it)
        for it in pieces:
            print('[%s] %s'%(it,pieces[it]))



if __name__ == '__main__':

    # testing()

    run()


