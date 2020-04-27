#!/usr/bin/env python
# -*- coding: utf-8 -*-

db_host     = '127.0.0.1'
db_user     = 'root'
db_password = ''
db_dbname   = 'mypubmed'

# ignore db error when insert, else stop and exit
ignore_db_error = True

#
low_memory = False

# pm_deletion: delete, markline, ignore
# how to deal with <DeleteCitation>
#   delete:     delete all rows in main-table and sub-table with this PMID, default
#   markline:   add new line PMID with `Status`='_DELETE_' in main-table
#   ignore:     do nothing
# markline is quite faster than delete, but after converted, 
# you must delete the previous line with the pmid
pm_deletion = 'delete'


xml_files_path  = ['/cygdrive/e/download/pubmed*.gz']

