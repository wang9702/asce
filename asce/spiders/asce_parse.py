# -*- coding: utf-8 -*-
# @Time    : 2021/8/18 9:37
# @Author  : WangCheng
# @File    : asce_new.py

# -*- coding: utf-8 -*-
import scrapy
import pymongo
import re
import datetime, time


class FullNetSpider(scrapy.Spider):
    name = 'asce_parse'
    allowed_domains = ['ascelibrary.org']
    start_urls = [
        'https://ascelibrary.org/action/showPublications?pubType=journal&target=browse&startPage=&pageSize=50']

    def __init__(self):

        self.header = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/75.0.3770.100 Safari/537.36'
        }
        # self.mongo_client = pymongo.MongoClient(host="117.119.77.139",
        #                                           port=30019,
        #                                           username="mongouser",
        #                                           password="YsuKeg0225",
        #                                           authSource="admin",
        #                                           authMechanism="SCRAM-SHA-1",
        #                                           )
        self.mongo_client = pymongo.MongoClient(host="127.0.0.1",
                                                  port=27017,
                                                  username="wang",
                                                  password="Wang@123",
                                                  authSource="admin",
                                                  authMechanism="SCRAM-SHA-1",
                                                  )
        self.db = self.mongo_client['publisher_journal_db']
        self.collection = self.db['taceat']
        self.collection.ensure_index('url', unique=True)

    def parse(self, response):
        journal_list = response.xpath('//div[@class="listBody"]/div/div[@class="rightSide"]/h2/a/@href').extract()
        for journal in journal_list:
            url = response.urljoin(journal)
            yield scrapy.Request(
                url=url,
                callback=self.parse_journal,
                headers=self.header
            )

    def parse_journal(self, response):
        issue_list = response.xpath('//div[@class="issues"]/div/div/div[@class="row "]/a/@href').extract()
        year_list = response.xpath(
            '//div[@class="issues"]/div/div/div[@class="row "]/span[@class="loiIssueCoverDateText"]/text()').extract()
        sid = response.url.split('/')[-1].strip()
        for issue, year in zip(issue_list, year_list):
            url = response.urljoin(issue)
            yield scrapy.Request(
                url=url,
                callback=self.parse_issue,
                headers=self.header,
                dont_filter=True,
                meta={'sid': sid}
            )

    def parse_issue(self, response):
        meta = response.meta
        issn = response.xpath(
            '//div[@class="issn-header-widget"]/div[@class="serial-item"]/span[@class="serial-value"][1]/text()').extract_first()
        eissn = response.xpath(
            '//div[@class="issn-header-widget"]/div[@class="serial-item"]/span[@class="serial-value"][2]/text()').extract_first()
        article_list = response.xpath(
            '//div[@class="tocContent"]/div[@li="cit-list"]/div/div/div/div[@class="art_title linkable"]/a/@href').extract()
        meta['issn'] = issn
        meta['eissn'] = eissn
        for article in article_list:
            url = response.urljoin(article)
            yield scrapy.Request(
                url=url,
                callback=self.parse_article,
                headers=self.header,
                dont_filter=True,
                meta=meta
            )

    def parse_article(self, response):
        item = {}
        item['ts'] = datetime.datetime.strptime(time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time())),
                                                '%Y-%m-%d %H:%M:%S')
        item['url'] = [response.url]
        lang = response.xpath('//html/@lang').extract_first()
        item['lang'] = lang
        title = ''.join(response.xpath(
            '//div[@class="hlFld-Title"]/div[@class="publicationContentTitle"]/h1//text()').extract()).strip()
        item['title'] = {lang: ' '.join(title.replace('\n', '').replace('\t', '').replace('\r', '').strip().split())}
        raw_title = response.xpath(
            '//div[@class="hlFld-Title"]/div[@class="publicationContentTitle"]/h1').extract_first()
        item['raw_title'] = {lang: raw_title}

        words = item['title'][lang].split()
        hash = ''
        for word in words:
            if word[0]:
                hash = hash + word[0].lower()
        item['hash'] = hash

        pdf_src = response.xpath('//ul[@class="ux3-inline "]/li[@class="coolBar__downlaod"]/a/@href').extract()
        if pdf_src:
            item['pdf_src'] = ['https://ascelibrary.org' + pdf_src[0]]

        item["year"] = int(response.xpath('//div[@class="journalNavTitle"]/a/text()').extract_first().split()[-1])
        item["volume"] = response.xpath('//div[@class="journalNavTitle"]/a/text()').extract_first().split()[1]
        item["issue"] = response.xpath('//div[@class="journalNavTitle"]/a/text()').extract_first().split()[3]
        doi = response.xpath('//div[@class="publicationContentDoi"]/a/text()').extract_first()
        if doi and re.findall(r'\((\d+)\)', doi):
            item['page_start'] = re.findall(r'\((\d+)\)', doi)[-1]
        paper_type = response.xpath(
            '//div[@class="article-top-region clearIt"]/div[@class="article-type"]/text()').extract_first()
        if paper_type:
            item['paper_type'] = paper_type

        item['issn'] = response.meta['issn']
        item['eissn'] = response.meta['eissn']

        if response.xpath('//section/strong[@class="subHeading"]/text()').extract_first() == 'ASCE Subject Headings: ':
            terms = response.xpath('//section/a/text()').extract()
            item['terms'] = {lang: ';'.join(terms)}

        date_str = response.xpath(
            '//div[@class="article-meta-byline"]/div[@class="publicationContentEpubDate dates"]/text()').extract_first()
        if date_str:
            item['date_str'] = date_str

        doi = response.xpath('//div[@class="publicationContentDoi"]/a/text()').extract_first()
        if doi:
            item['doi'] = doi
            sid = doi.split('/')[-1]
            item['sid'] = sid
        else:
            item['sid'] = response.url.split('/')[-1]

        src = 'ascelibrary'
        item['src'] = src

        venue = {'name': {lang: response.xpath(
            '//div[@class="journalMetaTitle page-heading"]/h1/a/span[@class="title"]/text()').extract_first()},
                 'type': 1, 'sid': response.meta['sid']}
        item['venue'] = venue

        author_list = response.xpath(
            '//div[@class="author-block"]/div[@class="authorName"]/a/span/span/text()').extract()
        if author_list:
            authors = []
            for i in range(len(author_list)):
                dic = {}
                dic['name'] = {lang: ' '.join(
                    author_list[i].replace('\n', '').replace('\r', '').replace('\t', '').replace('and', '').strip(
                        '., ').split())}
                dic['pos'] = i
                if response.xpath('//div[@class="author-block"][{}]/div[@class="authorAffiliation"]/text()'.format(
                        i + 1)).extract():
                    institution = ''.join(response.xpath(
                        '//div[@class="author-block"][{}]/div[@class="authorAffiliation"]/text()'.format(
                            i + 1)).extract())
                    if 'Email' in institution or 'E-mail' in institution and response.xpath(
                            '//div[@class="author-block"][{}]/div[@class="authorAffiliation"]/a[last()]/@href'.format(
                                i + 1)).extract():
                        emails = []
                        email_list = response.xpath(
                            '//div[@class="author-block"][{}]/div[@class="authorAffiliation"]/a[last()]/@href'.format(
                                i + 1)).extract()
                        if email_list and '/cdn-cgi/l/email-protection' not in email_list:
                            for email in email_list:
                                emails.append(self.decodeEmail(email.split('#')[1]))
                            dic['email'] = ';'.join(emails).strip()
                        elif response.xpath(
                                '//div[@class="author-block"][{}]/div[@class="authorAffiliation"]/a/@data-cfemail'.format(
                                    i + 1)).extract():
                            email_list = response.xpath(
                                '//div[@class="author-block"][{}]/div[@class="authorAffiliation"]/a/@data-cfemail'.format(
                                    i + 1)).extract()
                            for email in email_list:
                                emails.append(self.decodeEmail(email))
                            dic['email'] = ';'.join(emails).strip()
                    if 'ORCID' in institution:
                        dic['orcid'] = response.xpath(
                            '//div[@class="author-block"][{}]/div[@class="authorName"]/a[@class="orcid-link"]/@href'.format(
                                i + 1)).extract_first().split('/')[-1]
                    if 'corresponding author' in institution:
                        dic['is_corresponding'] = True
                    institution_list = [
                        institution.replace('. ORCID: ', '').replace('\n', '').replace('\r', '').replace('\t',
                                                                                                         '').replace(
                            'E-mail:', '').replace('Email:', '').replace('(corresponding author).', '').strip('.,; ')]
                    dic['org'] = institution_list
                authors.append(dic)
            item['authors'] = authors

        abstract = response.xpath(
            '//article[@class="article"]/div[@class="NLM_sec NLM_sec_level_1 hlFld-Abstract"]/p').extract_first()
        if abstract:
            item['abstract'] = {lang: abstract}

        reference_list = response.xpath('//div[@class="references"]').extract()
        if reference_list:
            references = []
            for reference in reference_list:
                references.append({lang: reference})
            item['reference'] = references

        data = {
            'ajax': 'true',
            'doi': '/'.join(doi.split('/')[-2:])
        }
        yield scrapy.FormRequest(
            url='https://ascelibrary.org/action/ajaxShowCitedBy',
            formdata=data,
            callback=self.parse_citation,
            headers=self.header,
            dont_filter=True,
            meta={'item': item}
        )

    def parse_citation(self, response):
        item = response.meta['item']
        citation_list = response.xpath('//div[@class="citedBySection"]/div[@class="citedByEntry"]').extract()
        if citation_list:
            citations = []
            for citation in citation_list:
                citations.append({item['lang']: citation})
            item['citation'] = citation_list
            self.save_to_mongo(dict(item))
        else:
            self.save_to_mongo(dict(item))

    def decodeEmail(self, input):
        email = ""
        a = int(input[0:2], 16)
        for i in range(2, len(input), 2):
            email += chr(int(input[i:i + 2], 16) ^ a)
        return email

    def save_to_mongo(self, item):
        try:
            if self.collection.insert(item):
                print('保存到MonGo成功')
        except Exception:
            print('存储到MonGo失败')
