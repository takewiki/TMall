# -*- coding: utf-8 -*-
import json
import time
from random import uniform
from selenium import webdriver
from selenium.webdriver import ActionChains
from dialogue.dumblog import dlog
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
import selenium.webdriver.support.ui as ui
from utils.redisq import RedisQueue
from pyquery import PyQuery as pq
logger = dlog(__file__, console='debug')
user_agent = 'Mozilla/5.0 (Windows NT 6.1) AppleWebKit/537.36 (KHTML, like Gecko) Iron/31.0.1700.0 Chrome/31.0.1700.0'

REDIS_IP = '127.0.0.1'
REDIS_PASS = ''
page_queue = RedisQueue('page', host=REDIS_IP, db=6, password=REDIS_PASS)
res_queue = RedisQueue('result', host=REDIS_IP, db=6, password=REDIS_PASS)


class TmallLogin(object):
    def __init__(self):
        self.driver = webdriver.PhantomJS(service_args=['--load-images=no'])
        self.action = ActionChains(self.driver)

    def sendinfo(self):
        self.driver.find_element_by_id('TPL_username_1').send_keys('用户名')
        self.driver.find_element_by_id('TPL_password_1').send_keys('密码')
        self.driver.find_element_by_id('J_SubmitStatic').click()

    def checkslipper(self):  # 验证滑块部分
        slipper = self.driver.find_element_by_css_selector('.nc-lang-cnt')
        h_position = slipper.location
        logger.info('-' * 30 + str(h_position))
        self.action.drag_and_drop_by_offset(slipper, h_position['x'] + 300, h_position['y']).perform()

    def login(self):
        logger.info("Login Tmall")
        self.driver.get("https://login.tmall.com/")
        login_iframe = self.driver.find_element_by_id("J_loginIframe")
        if not login_iframe:
            logger.warning('Not found tmall login iframe!')
            return
        self.driver.switch_to.frame(login_iframe)
        if self.driver.find_element_by_id('J_Quick2Static').is_displayed():
            self.driver.find_element_by_id('J_Quick2Static').click()
        time.sleep(0.5)
        slipper = self.driver.find_element_by_css_selector('.nc-lang-cnt')
        if slipper:  # 如果有滑块
            self.checkslipper()
        self.sendinfo()
        time.sleep(uniform(8, 12))
        self.driver.get_screenshot_as_file('pic/success.png')

    def wait_for_clickable(self, selector, timeout=10):
        WebDriverWait(self.driver, timeout).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
        )

    def wait_after_click(self, click, wait, timeout=10):
        comm_ele = self.driver.find_element_by_css_selector(click)
        comm_ele.click()
        WebDriverWait(self.driver, timeout).until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, wait))
        )

    def determine(self, element):  # 如果找到元素名，返回真，如果找不到，返回假
        try:
            self.driver.find_element_by_class_name(element)
            return True
        except BaseException:
            return False

    def choose_selector(self):  # 选择器分类
        dot_element = 'rate-page-break'
        result = self.determine(dot_element)
        print '--'*20
        print result
        print '--'*20
        if result is True:  # 如果有点点点的选择器
            next_page_selector = '.rate-page .rate-paginator .rate-page-break + a[data-page]'
            return next_page_selector
        else:
            next_page_selector = '.rate-page .rate-paginator a[data-page]'
            results = self.driver.find_elements_by_css_selector(next_page_selector)
            if len(results) == 1 and results[0].text == u'下一页>>':
                return next_page_selector
            elif len(results) == 2:  # 在中间的页码，有上一页和下一页时，有待检验
                return '.rate-page .rate-paginator a[data-page]:nth-child(5)'
            elif len(results) == 1 and results[0].text == u'<<上一页':
                pass  # 说明没有下一页了，不用再返回选择器了

    def crawler(self):
        # url = 'https://detail.tmall.com/item.htm?spm=a220m.1000858.1000725.10.5suWJ0&id=527680541344&skuId=3150349001482&areaId=320100&cat_id=2&rn=5d8121f40e659a29a6ed8dfce87ffcbd&user_id=2786278078&is_b=1'
        url = 'https://detail.tmall.com/item.htm?spm=a1z10.15-b.w4011-7524477099.99.XU8KX2&id=39578745679&rn=f879610ca3b5a66a8cd08f19a0cc2de2&abbucket=8'
        logger.info(url)
        logger.info('the url for collecting info!')
        self.driver.get(url)
        time.sleep(uniform(6, 8))
        self.driver.save_screenshot('pic/1.png')
        self.wait_for_clickable('.tm-selected')  # 等累计评论可以点击了
        self.driver.save_screenshot('pic/2.png')
        self.wait_after_click('.tm-selected', '.rate-grid')  # 点击(前面的)累计评价，等(后面的)评论区域出现
        wait = ui.WebDriverWait(self.driver, 10)
        wait.until(lambda driver: self.driver.find_element_by_id('footer'))
        self.driver.save_screenshot('pic/3.png')
        page_queue.put({'url': url, 'page': '1', 'html': self.driver.page_source})  # 将第一页的评论内容放入队列中
        time.sleep(uniform(2, 3))
        for page in xrange(2, 4):
            time.sleep(uniform(10, 20))
            logger.info(page)
            print '**'*20
            selector = self.choose_selector()
            print selector
            print '**'*20
            try:
                self.wait_for_clickable(selector)  # 等下一页的选择器出现
                self.driver.save_screenshot('pic/turnpage_1.png')
            except Exception, err:
                logger.info(err)
            self.wait_after_click(selector, '.rate-grid')  # 点击(前面的)下一页的选择器，等后面的评论区域出现
            self.driver.save_screenshot('pic/turnpage_2.png')
            time.sleep(uniform(2, 3))
            self.driver.save_screenshot('pic/screenshot_%s.png' % page)
            page_queue.put({'url': url, 'page': page, 'html': self.driver.page_source})  # 将翻页的内容放入队列中

    def parse(self):
        try:
            while not page_queue.empty():
                param = page_queue.get()
                dollar = pq(param['html'])
                res = {'page': param['page'],
                       'name': dollar('.tb-detail-hd h1[data-spm]').text(),
                       'id': dollar('#J_AddFavorite').attr('data-aldurl').split('=')[-1],
                       'review': dollar('#J_ItemRates .tm-indcon .tm-count').text(),
                       'price': dollar('#J_StrPriceModBox .tm-price').text(),
                       'service': [pq(i).attr('title') for i in dollar('.tb-serPromise li a')],
                       'choose-color': dollar('.tb-selected').attr('title'),
                       'shop': dollar('.shop-intro .hd .name a').text(),
                       'shop_describe': dollar('.main-info .shopdsr-item .shopdsr-score-con').eq(0).text(),
                       'shop_service': dollar('.main-info .shopdsr-item .shopdsr-score-con').eq(1).text(),
                       'shop_logistics': dollar('.main-info .shopdsr-item .shopdsr-score-con').eq(2).text(),
                       'collect': dollar('#J_CollectCount').text(),
                       'sell_num': dollar('.tm-indcon .tm-count').text().split()[0]}
                desc = {}
                for item in dollar('#J_AttrUL li'):
                    desc.update({pq(item).attr('title'): pq(item).text().strip()})
                res['product-desc'] = desc
                rate = dollar('.rate-score strong').text()
                comm_tags = [pq(i).text() for i in dollar('.rate-tag-inner span a')]
                res['comment'] = {'rate': rate, 'comm-tags': comm_tags,
                                  'comment-count': dollar('.J_ReviewsCount').text().split()[0],
                                  'img_num': dollar('.rate-filter label').eq(-1).text()}
                res['comment-detail'] = self.parse_comment(dollar)
                # return res
                res_queue.put(res)
        except BaseException as error:
            print error

    def parse_comment(self, dollar):
        comments = []
        for comm in dollar('.rate-grid tr'):
            d = pq(comm)
            comment = {
                'user': d('.rate-user-info').text(),
                'level': d('.rate-user-grade').text(),
                'comment-time': d('.tm-rate-date').text(),
                'product_color': d('.rate-sku>p').text(),
                'content': d('.tm-rate-content .tm-rate-fulltxt').text(),
                'add_content': d('.tm-rate-append').text(),
                'imgs': [pq(i).attr('src') for i in d('.tm-m-photos img')]
            }
            comments.append(comment)
        return comments

    def save(self):
        try:
            while not res_queue.empty():
                param = res_queue.get()
                res = json.dumps(param, sort_keys=True, indent=4).decode('unicode-escape').encode('utf8')
                with open('pic/tmall_%s_%s.json' % (param['id'], param['page']), 'w') as f:
                    f.write(res)
        except BaseException as error:
            print error
        # try:
        #     param = self.parse()
        #     res = json.dumps(param, sort_keys=True, indent=4).decode('unicode-escape').encode('utf8')
        #     with open('pic/tmall_%s_%s.json' % (param['id'], param['page']), 'w') as f:
        #         f.write(res)
        # except BaseException as error:
        #     print error

if __name__ == '__main__':
    agent = TmallLogin()
    agent.login()
    agent.crawler()
    agent.parse()
    agent.save()

