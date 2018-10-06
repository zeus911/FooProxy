#coding:utf-8

"""
    @author  : linkin
    @email   : yooleak@outlook.com
    @date    : 2018-10-05
"""

import time
from tools.util         import time_to_date
from tools.util         import get_ip_addr
from Helper.dbhelper    import Database
from DB.settings        import _DB_SETTINGS
from const.settings     import PRECISION
from config.config      import MIN_SUCCESS_RATE

class Rator(object):

    def __init__(self,db):
        self.raw_filter     = set()
        self.delete_filter  = set()
        self.db             = db

    def begin(self):
        self.db.connect()
        self.pull_table(self.db.table)

    def end(self):
        self.db.close()

    def pull_table(self,tname):
        if not tname:return
        table_data = self.db.all(tname)
        for i in table_data:
            if self.db.type == 'mongodb':
                self.raw_filter.add(':'.join([i['ip'],i['port']]))
            elif self.db.type == 'mysql':
                self.raw_filter.add(':'.join([i[1],i[2]]))
            else:
                raise TypeError('Illegal database backend :%s'%self.db.type)

    def mark_success(self,data):
        ip = data['ip']
        port = data['port']
        proxy = ':'.join([ip,port])
        valid_time = time_to_date(int(time.time()))
        data['valid_time'] = valid_time
        if proxy in self.raw_filter:
            if proxy not in self.delete_filter:
                self.mark_update(data)
                return
        else:
            address = get_ip_addr(ip)
            elapsed = round(int(data['resp_time'].replace('ms', '')) / 1000, 3)
            score = round(100 - 10 * (elapsed - 1), 2)
            stability = round(score/PRECISION,4)
            data['address'] = address
            data['score'] = score
            data['test_count'] = 1
            data['stability'] = stability
            data['success_rate'] = str(round(1 - (data['fail_count'] / data['test_count']),
                                             3) * 100) + '%'
            self.db.save(data)
            self.raw_filter.add(proxy)

    def mark_fail(self,data,db=None):
        ip = data['ip']
        port = data['port']
        update_data = {}
        _one_data = db.select({'ip': ip, 'port': port})
        if _one_data:
            _score = _one_data[5]
            _count = _one_data[8]
            _f_count = _one_data[9]
            _success_rate = _one_data[-2]
            valid_time = time_to_date(int(time.time()))
            update_data['score'] = _score-5
            update_data['test_count'] = _count+1
            update_data['fail_count'] = _f_count+1
            update_data['valid_time'] = valid_time
            success_rate = round(1 - (update_data['fail_count'] /
                                                         update_data['test_count']),
                                                    3)
            update_data['success_rate'] = str(success_rate* 100) + '%'
            update_data['stability'] = round(update_data['score']*update_data['test_count']*
                                             success_rate /PRECISION,4)
            if _count >= 100 and _success_rate <= str(MIN_SUCCESS_RATE*100)+'%':
                db.delete({'ip':ip,'port':port})
            else:
                print(ip)
                db.update({'ip':ip,'port':port},update_data)
                print(update_data)

    def mark_update(self,data):
        db      = Database(_DB_SETTINGS)
        db.table = self.db.table
        db.connect()
        ip      = data['ip']
        port    = data['port']
        valid_time = time_to_date(int(time.time()))
        data['valid_time'] = valid_time
        elapsed = round(int(data['resp_time'].replace('ms', '')) / 1000, 3)
        score = round(100 - 10 * (elapsed - 1), 2)
        _one_data = db.select({'ip':ip,'port':port})
        if _one_data:
            _score = _one_data[5]
            _count = _one_data[8]
            _f_count = _one_data[9]
            _address = _one_data[4]
            score = round((score+_score*_count)/(_count+1),2)
            address = get_ip_addr(ip) if _address=='unknown' else _address
            success_rate = round(1-(_f_count/(_count+1)),3)
            stability = round(score*(_count+1)*success_rate/PRECISION,4)
            data['address'] = address
            data['score'] = score
            data['test_count'] = _count+1
            data['success_rate'] = str(success_rate*100)+'%'
            data['stability'] = stability
            del data['fail_count']
            db.update({'ip':ip,'port':port},data)
            db.close()

