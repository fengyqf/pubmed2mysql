#!/usr/bin/env python
# -*- coding: utf-8 -*-
  
import sys
if sys.version_info < (3,0):
    exit('[Failed] python 3.x required')

import xml.etree.ElementTree as ET
from collections import OrderedDict
import re
import pymysql
import traceback
import config
import gzip
import glob



class CfgDocLevelType():
    def __init__(self):
        self.dl_types=[
            '<PubmedArticle>','<PubmedBookArticle>','<DeleteCitation>',
            '<BookDocument>','<DeleteDocument>'
            ]


# iterable object:
#   parse pubmed xml file to articles as xml-string
class PmaIter():
    # pubmed document-level elements tag, start/end
    def __init__(self,file_path):
        self.init_dt()
        if file_path.endswith('.gz'):
            self.file=gzip.open(file_path,'rt')
        else:
            self.file=open(file_path,'r')
        self.x_hdr=self.file.readline()
        self.buff=''
        self.bs=False
        self.tag_end=''

    def __iter__(self):
        return self

    def __next__(self):
        while True:
            line=self.file.readline()
            if line=='':
                break
            line_strip=line.strip()
            if line_strip in self.dl_s:
                # start buff fill
                self.bs=True
                self.buff=line
                self.tag_end=self.dl_e[self.dl_s.index(line_strip)]
            else:
                if not self.bs:
                    continue
                self.buff+=line
                if line_strip==self.tag_end:
                    self.bs=False
                    break
        if self.buff!='':
            buff=self.x_hdr+self.buff
            self.buff=''
            return buff
        else:
            self.file.close()
            raise StopIteration

    def init_dt(self):
        ''' init as:
        dl_s=['<PubmedArticle>','<PubmedBookArticle>','<DeleteCitation>',
              '<BookDocument>','<DeleteDocument>']
        dl_e=['</PubmedArticle>','</PubmedBookArticle>','</DeleteCitation>',
              '</BookDocument>','</DeleteDocument>']
        '''
        cfgdt=CfgDocLevelType()
        self.dl_s=cfgdt.dl_types
        self.dl_e=[it.replace('<','</') for it in self.dl_s]



class EtPmaIter(PmaIter):
    """docstring for EtPmaIter"""
    def __init__(self, file_path):
        super(EtPmaIter, self).__init__(file_path)
        self.file_path = file_path
        
    def __next__(self):
        pma=super(EtPmaIter, self).__next__()
        return ET.fromstring(pma)


# another way using generator
def parse_pm_as_et(file_path):
    pma=PmaIter(file_path)
    for art in pma:
        yield ET.fromstring(art)



'''
 *  BaseClass for parse single pubmed-doc,
 *  such as PubmedArticle/PubmedBookArticle/DeleteCitation...
'''
class ParseSingleBase():
    """docstring for ParseSingleBase"""
    def __init__(self, xet):
        self.xet=xet
        
    # extract the text or @attrib to buff-key
    def parse_single(self,xpath,attr,key):
        rtn=self.parse_all_by_xpath(xpath,attr,key)
        if len(rtn) == 1 :
            self.buff[key]=rtn[0]
            return True
        else:
            raise AssertionError('xpath not single: %s,  %s'%(len(rtn),xpath))

    def parse_one(self,xpath,attr,key):
        rtn=self.parse_all_by_xpath(xpath,attr,key)
        if len(rtn) >= 1 :
            self.buff[key]=rtn[0]
        else:
            self.buff[key]=None
        return True

    def parse_many(self,xpath,attr,key):
        rtn=self.parse_all_by_xpath(xpath,attr,key)
        self.buff[key]=rtn
        return True


    def parse_all_by_xpath(self,xpath,attr,key):
        ele=self.xet.findall(xpath)
        rtn=[]
        for i in range(len(ele)):
            val=None
            atrs=ele[i].attrib
            if attr=='text':
                val=ele[i].text
            elif attr[0]=='@' and attr[1:] in atrs :
                val=atrs[attr[1:]]
            else:
                val=None
            rtn.append(val)
        return rtn

    # extract date-string in sub-elements in xpath
    def extract_single_date_by_xpath(self,xpath,hourminute=False):
        ele=self.xet.findall(xpath)
        if len(ele)==0:
            return None
        assert len(ele)==1
        return self.extract_date_in_ele(ele[0],hourminute)

    def extract_date(self,xpath,hourminute=False):
        ele=self.xet.findall(xpath)
        if len(ele)==0:
            return None
        return self.extract_date_in_ele(ele[0],hourminute)


    def extract_date_in_ele(self,ele,hourminute=False):
        year=ele.find(r'./Year').text
        month=ele.find(r'./Month').text
        day=ele.find(r'./Day').text
        ymd=year.zfill(4)+month.zfill(2)+day.zfill(2)
        if not hourminute:
            return ymd
        else:
            e=ele.find(r'./Hour')
            hour=e.text if e!=None else '00'
            e=ele.find(r'./Minute')
            minute=e.text if e!=None else '00'
            return ymd+hour.zfill(2)+minute.zfill(2)

    def find_one_in_ele(self,ele,xpath,attr):
        tmp=ele.findall(xpath)
        if len(tmp)==0:
            return None
        e=tmp[0]
        atrs=e.attrib
        if attr=='text':
            val=e.text
        elif attr[0]=='@' and attr[1:] in atrs :
            val=atrs[attr[1:]]
        else:
            val=None
        return val

    def find_all_join_text_in_ele(self,ele,xpath,attr='text'):
        tmp=ele.findall(xpath)
        val=[it.text for it in tmp if isinstance(it.text,str)]
        return ' '.join(val)


# parse single PubmedArticle, xet is xml Element
class ParseSinglePubmedArticle(ParseSingleBase):
    """docstring for ParseSinglePubmedArticle"""
    def __init__(self, xet):
        super(ParseSinglePubmedArticle, self).__init__(xet)
        self.buff=OrderedDict()

    def parse(self):
        self.parse_single('.//MedlineCitation/PMID','text','PMID')
        self.parse_single('.//MedlineCitation','@Status','Status')
        self.parse_single('.//MedlineCitation','@IndexingMethod','IndexingMethod')
        self.parse_single('.//MedlineCitation','@Owner','Owner')
        self.parse_MedlineCitation_date()
        self.parse_single('.//MedlineCitation/Article','@PubModel','PubModel')
        self.parse_Journal()
        # seems almost/all Pagination uses MedlinePgn, so ignore StartPage/EndPage
        #self.parse_one('.//MedlineCitation/Article/Pagination/StartPage','text','StartPage')
        #self.parse_one('.//MedlineCitation/Article/Pagination/EndPage','text','EndPage')
        self.parse_one('.//MedlineCitation/Article/Pagination/MedlinePgn','text','MedlinePgn')
        # other EIdType of ELocationID ignored
        self.parse_one('.//MedlineCitation/Article/ELocationID[@EIdType="pii"]','text','ELocationID_pii')
        self.parse_one('.//MedlineCitation/Article/ELocationID[@EIdType="doi"]','text','ELocationID_doi')
        self.parse_Abstract()
        self.parse_one('.//MedlineCitation/Article/Abstract/CopyrightInformation','text','CopyrightInformation')
        self.parse_AuthorList()
        # Language is complex in fact
        self.parse_one('.//MedlineCitation/Article/Language','text','Language')
        self.parse_DataBankList()
        self.parse_GrantList()
        self.parse_PublicationTypeList()
        self.parse_one('.//MedlineCitation/Article/ArticleDate','@DateType','ArticleDate_DateType')
        self.buff['ArticleDate']=self.extract_date(r'.//MedlineCitation/Article/ArticleDate')
        self.parse_one('.//MedlineCitation/MedlineJournalInfo/Country','text','MedlineJournalInfo_Country')
        self.parse_one('.//MedlineCitation/MedlineJournalInfo/MedlineTA','text','MedlineJournalInfo_MedlineTA')
        self.parse_one('.//MedlineCitation/MedlineJournalInfo/NlmUniqueID','text','MedlineJournalInfo_NlmUniqueID')
        self.parse_one('.//MedlineCitation/MedlineJournalInfo/ISSNLinking','text','MedlineJournalInfo_ISSNLinking')
        self.parse_ChemicalList()
        self.parse_CitationSubset()
        self.parse_CommentsCorrectionsList()
        self.parse_MeshHeadingList()
        self.parse_one('.//MedlineCitation/CoiStatement','text','CoiStatement')
        self.parse_History_date()
        self.parse_one('.//PubmedData/PublicationStatus','text','PublicationStatus')
        self.parse_one('.//PubmedData/PublicationStatus','@UI','PublicationStatus_UI')
        self.parse_ArticleIdList()
        self.parse_KeywordList()
        self.parse_InvestigatorList()
        self.parse_ReferenceList()
        # <MedlineCitation>/<PersonalNameSubjectList>/<PersonalNameSubject> ignored
        return self.buff



    def parse_MedlineCitation_date(self):
        self.buff['DateCompleted']=self.extract_date(r'.//MedlineCitation/DateCompleted')
        self.buff['DateRevised']=self.extract_date(r'.//MedlineCitation/DateRevised')
        return None

    def parse_Journal(self):
        self.parse_one('.//MedlineCitation/Article/Journal/Title','text','Journal_Title')
        self.parse_one('.//MedlineCitation/Article/Journal/ISOAbbreviation','text','Journal_ISOAbbreviation')
        self.parse_one('.//MedlineCitation/Article/Journal/ISSN','@IssnType','IssnType')
        self.parse_one('.//MedlineCitation/Article/Journal/ISSN','text','ISSN')
        ele=self.xet.find(r'.//MedlineCitation/Article/Journal/JournalIssue')
        self.buff['CitedMedium']=self.find_one_in_ele(ele,'.','@CitedMedium')
        self.buff['Issue']=self.find_one_in_ele(ele,'./Issue','text')
        self.buff['Volume']=self.find_one_in_ele(ele,'./Volume','text')
        #self.parse_one('.//MedlineCitation/Article/Journal/JournalIssue','@CitedMedium','CitedMedium')
        #self.parse_one('.//MedlineCitation/Article/Journal/JournalIssue/Volume','text','Volume')
        #self.parse_one('.//MedlineCitation/Article/Journal/JournalIssue/Issue','text','Issue')
        self.buff['PubDate']=None    # placehold and fill later
        self.parse_one('.//MedlineCitation/Article/Journal/JournalIssue/PubDate/Year','text','PubDate_Year')
        self.parse_one('.//MedlineCitation/Article/Journal/JournalIssue/PubDate/Month','text','PubDate_Month')
        self.parse_one('.//MedlineCitation/Article/Journal/JournalIssue/PubDate/Day','text','PubDate_Day')
        self.parse_one('.//MedlineCitation/Article/Journal/JournalIssue/PubDate/Season','text','PubDate_Season')
        self.parse_one('.//MedlineCitation/Article/Journal/JournalIssue/PubDate/MedlineDate','text','PubDate_MedlineDate')
        mapping_month={
            'spring':'02','summer':'05','fall':'08','winter':'11','autumn':'08',
            'Spring':'02','Summer':'05','Fall':'08','Winter':'11','Autumn':'08',
            'Jan':'1', 'Feb':'2', 'Mar':'3', 'Apr':'4', 
            'May':'5', 'Jun':'6', 'Jul':'7', 'Aug':'8', 
            'Sep':'9', 'Oct':'10', 'Nov':'11', 'Dec':'12'}
        if self.buff['PubDate_Season'] != None:
            if self.buff['PubDate_Season'] in mapping_month:
                self.buff['PubDate_Month']=mapping_month[self.buff['PubDate_Season']]
                self.buff['PubDate_Day']='00'
        if self.buff['PubDate_MedlineDate'] != None:
            match=re.search(r'\d{4}',self.buff['PubDate_MedlineDate'])
            year=match.group(0)
            if year != None:
                self.buff['PubDate_Year']=year
            match=re.search('Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|Spring|Summer|Fall|Winter|Autumn'
                ,self.buff['PubDate_MedlineDate'])
            tmp=None
            if match != None:
                tmp=match.group(0)
            if tmp != None and tmp in mapping_month:
                self.buff['PubDate_Month']=mapping_month[tmp]
            self.buff['PubDate_Day']='00'   # ignore Day in MedlineDate
        # convert PubDate_Month to numeric
        if self.buff['PubDate_Month'] in mapping_month:
            self.buff['PubDate_Month']=mapping_month[self.buff['PubDate_Month']]
        year='0000' if self.buff['PubDate_Year']==None else self.buff['PubDate_Year']
        month='00' if self.buff['PubDate_Month']==None else self.buff['PubDate_Month']
        day = '00' if self.buff['PubDate_Day']==None else self.buff['PubDate_Day']
        self.buff['PubDate']='%s%s%s'%(year.zfill(4),month.zfill(2),day.zfill(2))
        # keep Year/Month, drop other sub-elements of PubDate
        del self.buff['PubDate_Day']
        del self.buff['PubDate_Season']
        del self.buff['PubDate_MedlineDate']


    def parse_Abstract(self):
        ele=self.xet.findall('.//MedlineCitation/Article/Abstract/AbstractText')
        self.buff['Abstract']=[]
        for i in range(len(ele)):
            tmp=OrderedDict()
            tmp['Label']=ele[i].attrib['Label'] if 'Label' in ele[i].attrib else None
            tmp['NlmCategory']=ele[i].attrib['NlmCategory'] if 'NlmCategory' in ele[i].attrib else None
            tmp['AbstractText']=ele[i].text
            self.buff['Abstract'].append(tmp)
        return None


    def parse_AuthorList(self):
        self.buff['AuthorList']=self.extract_AuthorList(r'.//MedlineCitation/Article/AuthorList/Author')
        return None

    def parse_DataBankList(self):
        ele=self.xet.findall('.//MedlineCitation/Article/DataBankList/DataBank')
        self.buff['DataBankList']=[]
        rtn=[]
        for i in range(len(ele)):
            name=self.find_one_in_ele(ele[i],r'./DataBankName','text')
            e=ele[i].findall(r'./AccessionNumberList/AccessionNumber')
            for j in range(len(e)):
                tmp=OrderedDict()
                tmp['DataBankName']=name
                tmp['AccessionNumber']=e[j].text
                rtn.append(tmp)
        self.buff['DataBankList']=rtn
        return None

    def parse_GrantList(self):
        self.parse_one('.//MedlineCitation/Article/GrantList','@CompleteYN','GrantList_CompleteYN')
        ele=self.xet.findall(r'.//MedlineCitation/Article/GrantList/Grant')
        self.buff['GrantList']=[]
        for i in range(len(ele)):
            tmp=OrderedDict()
            tmp['GrantID']=self.find_one_in_ele(ele[i],r'./GrantID','text')
            tmp['Acronym']=self.find_one_in_ele(ele[i],r'./Acronym','text')
            tmp['Agency']=self.find_one_in_ele(ele[i],r'./Agency','text')
            tmp['Country']=self.find_one_in_ele(ele[i],r'./Country','text')
            self.buff['GrantList'].append(tmp)
        return None

    def parse_PublicationTypeList(self):
        self.parse_many(r'.//MedlineCitation/Article/PublicationTypeList/PublicationType',
                    '@UI','tmp_UI')
        self.parse_many(r'.//MedlineCitation/Article/PublicationTypeList/PublicationType',
                    'text','tmp_text')
        assert len(self.buff['tmp_UI'])==len(self.buff['tmp_text'])
        self.buff['PublicationTypeList']=[]
        for i in range(len(self.buff['tmp_UI'])):
            tmp=OrderedDict()
            tmp['PublicationType_text']=self.buff['tmp_text'][i]
            tmp['PublicationType_UI']=self.buff['tmp_UI'][i]
            self.buff['PublicationTypeList'].append(tmp)
        del self.buff['tmp_UI']
        del self.buff['tmp_text']
        return None

    def parse_ChemicalList(self):
        ele=self.xet.findall('.//MedlineCitation/ChemicalList/Chemical')
        self.buff['ChemicalList']=[]
        for i in range(len(ele)):
            tmp=OrderedDict()
            tmp['RegistryNumber']=self.find_one_in_ele(ele[i],r'./RegistryNumber','text')
            tmp['NameOfSubstance_UI']=self.find_one_in_ele(ele[i],r'./NameOfSubstance','@UI')
            tmp['NameOfSubstance_text']=self.find_one_in_ele(ele[i],r'./NameOfSubstance','text')
            self.buff['ChemicalList'].append(tmp)
        return None

    def parse_CitationSubset(self):
        self.parse_many('.//MedlineCitation/CitationSubset','text','CitationSubset')
        tmp=[]
        for i in range(len(self.buff['CitationSubset'])):
            tmp.append(OrderedDict({'CitationSubset':self.buff['CitationSubset'][i]}))
        del self.buff['CitationSubset']
        self.buff['CitationSubset']=tmp
        return None

    def parse_CommentsCorrectionsList(self):
        ele=self.xet.findall(r'.//MedlineCitation/CommentsCorrectionsList/CommentsCorrections')
        self.buff['CommentsCorrectionsList']=[]
        for i in range(len(ele)):
            tmp=OrderedDict()
            tmp['RefType']=ele[i].attrib['RefType'] if 'RefType' in ele[i].attrib else ''
            tmp['RefSource']=self.find_one_in_ele(ele[i],'./RefSource','text')
            tmp['PMID']=self.find_one_in_ele(ele[i],'./PMID','text')
            tmp['Note']=self.find_one_in_ele(ele[i],'./Note','text')
            self.buff['CommentsCorrectionsList'].append(tmp)
        return None

    def parse_MeshHeadingList(self):
        ele=self.xet.findall('.//MedlineCitation/MeshHeadingList/MeshHeading')
        self.buff['MeshHeadingList']=[]
        for i in range(len(ele)):
            dname=self.find_one_in_ele(ele[i],r'./DescriptorName','text')
            dui=self.find_one_in_ele(ele[i],r'./DescriptorName','@UI')
            dmj=self.find_one_in_ele(ele[i],r'./DescriptorName','@MajorTopicYN')
            e=ele[i].findall(r'./QualifierName')
            if len(e) > 0:
                for j in range(len(e)):
                    tmp=OrderedDict()
                    tmp['DescriptorName_text']=dname
                    tmp['DescriptorName_UI']=dui
                    tmp['DescriptorName_MajorTopicYN']=dmj
                    tmp['QualifierName_text']=e[j].text
                    tmp['QualifierName_UI']=e[j].attrib['UI'] if 'UI' in e[j].attrib else None
                    tmp['QualifierName_MajorTopicYN']=\
                        e[j].attrib['MajorTopicYN'] if 'MajorTopicYN' in e[j].attrib else None
                    self.buff['MeshHeadingList'].append(tmp)
            else:
                tmp=OrderedDict()
                tmp['DescriptorName_text']=dname
                tmp['DescriptorName_UI']=dui
                tmp['DescriptorName_MajorTopicYN']=dmj
                tmp['QualifierName_text']=None
                tmp['QualifierName_UI']=None
                tmp['QualifierName_MajorTopicYN']=None
                self.buff['MeshHeadingList'].append(tmp)
        return None

    def parse_History_date(self):
        dts=self.extract_all_PubMedPubDate()
        self.buff['History']=dts
        self.buff['PubMedPubDate_pubmed']=None
        self.buff['PubMedPubDate_medline']=None
        self.buff['PubMedPubDate_entrez']=None
        for it in dts:
            if it['PubStatus']=='pubmed':
                self.buff['PubMedPubDate_pubmed']=it['date']
            if it['PubStatus']=='medline':
                self.buff['PubMedPubDate_medline']=it['date']
            if it['PubStatus']=='entrez':
                self.buff['PubMedPubDate_entrez']=it['date']
        return None

    def parse_ArticleIdList(self):
        dts=self.extract_all_ArticleIdList()
        self.buff['ArticleIdList']=dts
        self.buff['ArticleId_pubmed']=None
        self.buff['ArticleId_doi']=None
        self.buff['ArticleId_pmc']=None
        for it in dts:
            if it['IdType']=='pubmed':
                self.buff['ArticleId_pubmed']=it['ArticleId']
            if it['IdType']=='medline':
                self.buff['ArticleId_doi']=it['ArticleId']
            if it['IdType']=='entrez':
                self.buff['ArticleId_pmc']=it['ArticleId']
        return None

    def parse_KeywordList(self):
        ele=self.xet.findall(r'.//MedlineCitation/KeywordList')
        rtn=[]
        for i in range(len(ele)):
            owner=ele[i].attrib['Owner'] if 'Owner' in ele[i].attrib else 'NLM'
            e=ele[i].findall(r'./Keyword')
            for j in range(len(e)):
                tmp=OrderedDict()
                tmp['Keyword']=e[j].text
                tmp['MajorTopicYN']=e[j].attrib['MajorTopicYN'] if 'MajorTopicYN' in e[j].attrib else 'N'
                tmp['Owner']=owner
                rtn.append(tmp)
        self.buff['KeywordList']=rtn
        return None

    def parse_InvestigatorList(self):
        ele=self.xet.findall(r'.//MedlineCitation/InvestigatorList/Investigator')
        self.buff['InvestigatorList']=[]
        for i in range(len(ele)):
            tmp=OrderedDict()
            tmp['LastName']=self.find_one_in_ele(ele[i],'./LastName','text')
            tmp['ForeName']=self.find_one_in_ele(ele[i],'./ForeName','text')
            tmp['Initials']=self.find_one_in_ele(ele[i],'./Initials','text')
            tmp['Suffix']=self.find_one_in_ele(ele[i],'./Suffix','text')
            tmp['Identifier']=self.find_one_in_ele(ele[i],'./Identifier','text')
            tmp['AffiliationInfo']=self.find_one_in_ele(ele[i],'./AffiliationInfo','text')
            self.buff['InvestigatorList'].append(tmp)
        return None

    # pity that ReferenceList was Not found in  pubmed_180101.dtd (PubMed DTD)
    # assume: each reference has only one ArticleId in ArticleIdList,
    #   and all ArticleId use pubmed/pmid, ignore others.
    def parse_ReferenceList(self):
        ele=self.xet.findall(r'.//PubmedData/ReferenceList/Reference')
        rtn=[]
        for i in range(len(ele)):
            tmp=OrderedDict()
            e=ele[i].find('./Citation')
            tmp['Citation']=e.text if e != None else None
            e=ele[i].find(r'./ArticleIdList/ArticleId[@IdType="pubmed"]')
            tmp['ArticleId_pmid']=e.text if e!=None else None
            rtn.append(tmp)
        self.buff['ReferenceList']=rtn
        return None


    def extract_AuthorList(self,xpath):
        ele=self.xet.findall(xpath)
        authors=[]
        for i in range(len(ele)):
            au=OrderedDict()
            au['ValidYN']=ele[i].attrib['ValidYN'] if 'ValidYN' in ele[i].attrib else None
            au['LastName']=self.find_one_in_ele(ele[i],r'./LastName','text')
            au['ForeName']=self.find_one_in_ele(ele[i],r'./ForeName','text')
            au['Initials']=self.find_one_in_ele(ele[i],r'./Initials','text')
            au['Suffix']=self.find_one_in_ele(ele[i],r'./Suffix','text')
            au['CollectiveName']=self.find_one_in_ele(ele[i],r'./CollectiveName','text')
            au['Identifier']=self.find_one_in_ele(ele[i],r'./Identifier','text')
            au['Identifier_Source']=self.find_one_in_ele(ele[i],r'./Identifier','@Source')
            au['Affiliation']=self.find_all_join_text_in_ele(ele[i],r'./AffiliationInfo/Affiliation','text')
            authors.append(au)
        return authors

    def extract_all_PubMedPubDate(self):
        ele=self.xet.findall(r'.//PubmedData/History/PubMedPubDate')
        rtn=[]
        for i in range(len(ele)):
            tmp=OrderedDict()
            if 'PubStatus' not in ele[i].attrib:
                continue
            tmp['PubStatus']=ele[i].attrib['PubStatus'] 
            tmp['date']=self.extract_date_in_ele(ele[i],hourminute=True)
            rtn.append(tmp)
        return rtn

    def extract_all_ArticleIdList(self):
        ele=self.xet.findall(r'.//PubmedData/ArticleIdList/ArticleId')
        rtn=[]
        for i in range(len(ele)):
            tmp=OrderedDict()
            if 'IdType' not in ele[i].attrib:
                continue
            tmp['IdType']=ele[i].attrib['IdType'] 
            tmp['ArticleId']=ele[i].text
            rtn.append(tmp)
        return rtn



class ParseSingleBookDocumentSet(ParseSingleBase):
    """docstring for ParseSingleBookDocumentSet"""
    def __init__(self, xet):
        super(ParseSingleBookDocumentSet, self).__init__(xet)
        self.buff=OrderedDict()

    def parse(self):
        raise NotImplementedError('ParseSingleBookDocumentSet Not Implemented.')


# parse <DeleteCitation>
class ParseSingleDeleteCitation(ParseSingleBase):
    """docstring for ParseSingleDeleteCitation"""
    def __init__(self, xet):
        super(ParseSingleDeleteCitation, self).__init__(xet)
        self.buff=OrderedDict()
        #self.xet=xet

    def parse(self):
        self.parse_many('.//PMID','text','PMID')
        return self.buff


# parse <DeleteCitation>
class ParseSingleDeleteDocument(ParseSingleBase):
    """docstring for ParseSingleDeleteCitation"""
    def __init__(self, xet):
        super(ParseSingleDeleteCitation, self).__init__(xet)
        self.buff=OrderedDict()
        #self.xet=xet

    def parse(self):
        self.parse_many('.//PMID','text','PMID')
        return self.buff



class ParsePubmedDocument():
    """docstring for ParseSingleBase"""
    def __init__(self, xet):
        self.xet=xet
        tag=self.xet.find('.').tag
        self.type=tag
        self.parse()

    def parse(self):
        if self.type=='PubmedArticle':
            psr=ParseSinglePubmedArticle(self.xet)
        elif self.type=='DeleteCitation':
            psr=ParseSingleDeleteCitation(self.xet)
        elif self.type=='DeleteDocument':
            psr=ParseSingleDeleteDocument(self.xet)
        elif self.type=='BookDocumentSet':
            psr=ParseSingleBookDocumentSet(self.xet)
        else:
            #psr=ParseSingleBase(self.xet)
            #print('[Warnning] skipped UNKNOWN pubmed doc type: %s'%self.type)
            raise NotImplementedError('UNKNOWN pubmed doc type: %s'%self.type)
        psr.parse()
        buff=psr.buff
        self.buff=buff
        return buff


class PersistenceBase():
    def __init__(self, conn):
        self.conn=conn
        self.cursor=conn.cursor()
        self.cursor.execute('SELECT DATABASE()')
        self.db=self.cursor.fetchone()[0]

    def persistence(self,data):
        # main table values; and cache all sub table values
        main={}
        sub={}
        for key in data:
            if isinstance(data[key], list):
                main['%s__cnt'%key]=len(data[key])
                values=[]
                for row in data[key]:
                    if 'PMID' not in row:
                        row['PMID']=data['PMID']
                    values.append(row)
                table='%s%s'%(self.prefix,key)
                sub[table]=values
            else:
                main[key]=data[key]
        self.save_main(main)
        for table in sub:
            self.save_sub(table, sub[table])
        return None

    def save_main(self,values):
        sql="INSERT INTO `%s` (`%s`) VALUES(%s)"%(self.main_table
                , '`, `'.join(values.keys())
                , ', '.join([r'%s']*len(values))
            )
        val=[values[it] for it in values]
        try:
            self.cursor.execute(sql,val)
        except pymysql.err.IntegrityError:
            self.clean_pmid(values['PMID'])
            self.cursor.execute(sql,val)
        except:
            print(sql)
            print(val)
            traceback.print_exc()
            if not config.ignore_db_error:
                sys.exit()
        return None

    def save_sub(self,table,rows):
        for row in rows:
            self._save_one_sub(table,row)
        return None

    def _save_one_sub(self,table,values=OrderedDict()):
        sql="INSERT INTO `%s` (`%s`) VALUES(%s)"%(table
                , '`, `'.join(values.keys())
                , ', '.join([r'%s']*len(values))
            )
        val=[values[it] for it in values]
        try:
            self.cursor.execute(sql,val)
        except:
            print(sql)
            print(val)
            traceback.print_exc()
            if not config.ignore_db_error:
                sys.exit()
        self.conn.commit()
        return None

    def clean_pmid(self,pmid):
        for table in self.sub_tables+[self.main_table]:
            sql="DELETE FROM %s WHERE `PMID`=%s"%(table,pmid)
            try:
                self.cursor.execute(sql)
            except:
                print(sql)
                traceback.print_exc()
                sys.exit()
        return None



class PersistencePubmedArticle(PersistenceBase):
    prefix='pm_'
    subs=['Abstract','AuthorList','DataBankList','GrantList'
        ,'PublicationTypeList','ChemicalList','CitationSubset'
        ,'CommentsCorrectionsList','MeshHeadingList','History','ArticleIdList'
        ,'KeywordList','InvestigatorList','ReferenceList'
        ]
    def __init__(self, conn):
        super(PersistencePubmedArticle, self).__init__(conn)
        self.main_table="%smain"%self.prefix
        self.sub_tables=["%s%s"%(self.prefix,it) for it in self.subs]



# ------------------------------------------------------------------------------
def parse_xml_and_convert(file_path,conn):
    print("reading file: %s"%file_path)
    pers_article=PersistencePubmedArticle(conn)
    pma=EtPmaIter(file_path)
    i=0
    print('parsing...',end='',flush=True)
    for art in pma:
        psr=ParsePubmedDocument(art)
        if psr.type=='PubmedArticle':
            pers_article.persistence(psr.buff)
            if i % 10000 == 0:
                print("\n    %s  PMID=%s "%(i,psr.buff['PMID']),end='',flush=True)
            elif i % 250 == 0:
                print(".",end='',flush=True)
        else:
            raise Exception('UNKNOWN block: %s'%psr.type)
        i+=1
    print('\n%s lines converted\n'%i)


def run_parse_xml_files(xml_files_path,conn):
    files=glob.glob(xml_files_path)
    files.sort()
    for f in files:
        parse_xml_and_convert(f,conn)



# ------------------------------------------------------------------------------

if __name__ == '__main__':
    file_path = config.xml_files_path
    conn=pymysql.connect(config.db_host
                        ,config.db_user
                        ,config.db_password
                        ,config.db_dbname
                        )
    run_parse_xml_files(config.xml_files_path,conn)


