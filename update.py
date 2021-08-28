import pymongo

# client=pymongo.MongoClient('mongodb://localhost:27017')
client = pymongo.MongoClient(host="127.0.0.1",
                             port=27017,
                             username="wang",
                             password="Wang@123",
                             authSource="admin",
                             authMechanism="SCRAM-SHA-1",
                             )
db = client.ysu
collection = db.bmj_journals_urls_col_crawling

for i, item in enumerate(collection.find().skip(398565).batch_size(2)):
    with open('count.txt', 'w') as f:
        f.write(str(i))
    if item.get('paper_type'):
        url = item.get('url')
        if item.get('paper_type') == 'The ':
            paper_type = 'The JECH Gallery'
        elif item.get('paper_type') == 'Additional articles abstracted in ':
            paper_type = 'Additional articles abstracted in ACP Journal Club'
        else:
            paper_type = ' '.join(item.get('paper_type').split())
        try:
            if collection.update_one({'url': url}, {'$set': {'paper_type': paper_type}}):
                print("更新成功")
        except Exception as e:
            print(e)
    else:
        print("没有paper_type")
