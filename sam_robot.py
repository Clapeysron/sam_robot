#!/usr/bin/env python3
import requests
import json
import datetime
import time
from enum import IntEnum

# 需要抓包填入的字段
DEVICE_ID = ''
AUTHTOKEN = ''
# 配送方式
DELIVERY_TYPE = '2' # 1-极速达 / 2-全城送
# 是否使用固定的期望配送时间，留空则轮训服务器是否有可用时间
CONST_START_TIME = "" #"2022-04-22 09:00:00"
CONST_END_TIME = "" #"2022-04-22 21:00:00"
# 间隔设置
RETRY_TIME = 20 # 如果无可用配送时间，__秒后重新尝试
LIMIT_RETRY_TIME = 1 # 如果访问堵塞，__秒后重新尝试
TIMEOUT_DURATION = 10 # 发包超时时间
REFRESH_CART_TIME = 3 # 如果一直无可用配送时间，尝试__次后重新刷新一下购物车
# 企业微信机器人通知
WECOM_ROBOT_URL = "" # https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=

public_url = "https://api-sams.walmartmobile.cn"
public_headers = {
	'Host': 'api-sams.walmartmobile.cn',
	'Connection': 'keep-alive',
	'Accept': '*/*',
	'Accept-Encoding': 'gzip, deflate',
	'Accept-Language': 'zh-CN,zh;q=0.9',
	'User-Agent': 'SamClub/5.0.47 (iPhone; iOS 15.4.1; Scale/3.00)',
	'device-name': 'iPhone13,3',
	'device-os-version': '15.4.1',
	'device-id': DEVICE_ID,
	'device-type': 'ios',
	'auth-token': AUTHTOKEN,
	'app-version': '5.0.47.0'
}

class RET_CODE(IntEnum):
	SUCCESS = 0,
	EXCEPTION = 1,
	NO_DELIVERY_TIME = 2, # 没有可用配送时间
	NOT_DELIVERY_CAPACITY_ERROR = 3, # 当前可用配送时间已约满
	DECREASE_CAPACITY_COUNT_ERROR = 4, # 扣减运力失败
	LIMITED = 3, # 访问限制
	STORE_HAS_CLOSED = 4, # 商店关门
	OUT_OF_STOCK = 5, # 商品缺货
	UNKNOWN_ERROR = 6, # 未知错误
	
def UnixTime(dt):
	timeArray = time.strptime(dt, "%Y-%m-%d %H:%M:%S")
	timestamp = time.mktime(timeArray)
	return str(int(timestamp * 1000))

def FormatTime(unix_t):
	display_time = time.localtime(int(unix_t) / 1000)
	return time.strftime("%Y-%m-%d %H:%M:%S", display_time)

def CurrentTime():
	return time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time()))

def WeComNotify(log):
	if WECOM_ROBOT_URL != "":
		msg = {"msgtype": "text", "text": {"content": log[:2048]}}
		ret = requests.post(WECOM_ROBOT_URL, json = msg, timeout = TIMEOUT_DURATION)
		if ret.status_code != 200 or ret.json()["errcode"] != 0:
			print('--- 企业微信机器人设置错误')

def GetAddressList():
	print(f'- 获取收货地址列表 {CurrentTime()} -')
	url = public_url + '/api/v1/sams/sams-user/receiver_address/address_list'
	try:
		ret = requests.get(url = url, headers = public_headers, timeout = TIMEOUT_DURATION)
		ret_json = json.loads(ret.text)
		if ret_json['success']:
			return RET_CODE.SUCCESS, ret_json['data'].get('addressList')
		elif ret_json['code'] == 'LIMITED':
			return RET_CODE.LIMITED, None
		else:
			print(f"--- [Error] {ret_json['code']} {ret_json['msg']}")
			return RET_CODE.UNKNOWN_ERROR, None
	except Exception as e:
		print(f"--- [Exception] {str(e)}")
		return RET_CODE.EXCEPTION, None

def SelectAddress(address_list):
	try:
		for i in range(len(address_list)):
			name = str(address_list[i].get('name'))
			mobile = str(address_list[i].get('mobile'))
			districtName = str(address_list[i].get('districtName'))
			receiverAddress = str(address_list[i].get('receiverAddress'))
			detailAddress = str(address_list[i].get('detailAddress'))
			print(f"[{i}] {name} {mobile} {districtName} {receiverAddress}{detailAddress}")
		print(f"- 输入编号选择地址：", end = "")
		id_selected = int(input())
		print()
		address_selected = address_list[id_selected]
		public_headers.update({"latitude": address_selected["latitude"], "longitude": address_selected["longitude"]})
		return RET_CODE.SUCCESS, address_selected
	except Exception as e:
		print(f"--- [Exception] {str(e)}")
		return RET_CODE.EXCEPTION, None

def SaveDeliveryAddress(address_selected, personal_info):
	url = public_url + '/api/v1/sams/trade/cart/saveDeliveryAddress'
	try:
		headers = public_headers.copy()
		headers.update({ "Content-Type": 'application/json' })
		data = {
			"uid": personal_info.get("uid"),
			"addressId": address_selected.get("addressId")
		}
		ret = requests.post(url = url, headers = headers, data = json.dumps(data), timeout = TIMEOUT_DURATION)
		ret_json = json.loads(ret.text)
		if ret_json['success']:
			return RET_CODE.SUCCESS
		elif ret_json['code'] == 'LIMITED':
			return RET_CODE.LIMITED
		else:
			print(f"--- [Error] {ret_json['code']} {ret_json['msg']}")
			return RET_CODE.UNKNOWN_ERROR
	except Exception as e:
		print(f"--- [Exception] {str(e)}")
		return RET_CODE.EXCEPTION, None	

def GetStoreList():
	print(f'- 获取可用商店列表 {CurrentTime()} -')
	url = public_url + '/api/v1/sams/merchant/storeApi/getRecommendStoreListByLocation'
	try:
		headers = public_headers.copy()
		headers.update({ "Content-Type": 'application/json' })
		data = {
			'longitude': public_headers['longitude'],
			'latitude': public_headers['latitude'],
		}
		ret = requests.post(url = url, headers = headers, data = json.dumps(data), timeout = TIMEOUT_DURATION)
		ret_json = json.loads(ret.text)
		if ret_json['success']:
			store_list = []
			for store in json.loads(ret.text)['data'].get('storeList'):
				store_list.append({
					'storeType': store.get("storeType"),
					'storeId': store.get("storeId"),
					'areaBlockId': store.get('storeAreaBlockVerifyData').get("areaBlockId"),
					'storeDeliveryTemplateId': store.get('storeRecmdDeliveryTemplateData').get("storeDeliveryTemplateId"),
					'deliveryModeId': store.get('storeDeliveryModeVerifyData').get("deliveryModeId"),
					'storeName': store.get("storeName")
				})
			return RET_CODE.SUCCESS, store_list
		elif ret_json['code'] == 'LIMITED':
			return RET_CODE.LIMITED, None
		else:
			print(f"--- [Error] {ret_json['code']} {ret_json['msg']}")
			return RET_CODE.EXCEPTION, None
	except Exception as e:
		print(f"--- [Exception] {str(e)}")
		return RET_CODE.EXCEPTION, None

def SelectStore(store_list):
	try:
		for i in range(len(store_list)):
			storeId = store_list[i].get('storeId')
			storeName = store_list[i].get('storeName')
			print(f"[{i}] {storeId} {storeName}")
		print(f"- 输入编号选择配送商店：", end = "")
		id_selected = int(input())
		print()
		return RET_CODE.SUCCESS, store_list[id_selected]
	except Exception as e:
		print(f"--- [Exception] {str(e)}")
		return RET_CODE.EXCEPTION, None

def GetPersonalCenterInfo():
	url = public_url + '/api/v1/sams/sams-user/user/personal_center_info'
	try:
		ret = requests.get(url = url, headers = public_headers, timeout = TIMEOUT_DURATION)
		ret_json = json.loads(ret.text)
		if ret_json['success']:
			return RET_CODE.SUCCESS, ret_json['data']['memInfo']
		elif ret_json['code'] == 'LIMITED':
			return RET_CODE.LIMITED, None
		else:
			print(f"--- [Error] {ret_json['code']} {ret_json['msg']}")
			return RET_CODE.UNKNOWN_ERROR, None
	except Exception as e:
		print(f"--- [Exception] {str(e)}")
		return RET_CODE.EXCEPTION, None
	
def GetUserCart(personal_info, store_list):
	print(f'- 获取购物车列表 {CurrentTime()} -')
	url = public_url + '/api/v1/sams/trade/cart/getUserCart'
	try:
		headers = public_headers.copy()
		headers.update({ "Content-Type": 'application/json' })
		data = {
			"uid": personal_info.get("uid"),
			"deliveryType": DELIVERY_TYPE,
			"deviceType": "ios",
			"storeList": store_list,
			"parentDeliveryType": 1,
			"homePagelongitude": public_headers['longitude'],
			"homePagelatitude": public_headers['latitude'],
		}
		ret = requests.post(url = url, headers = headers, data = json.dumps(data), timeout = TIMEOUT_DURATION)
		ret_json = json.loads(ret.text)
		if ret_json['success']:
			normalGoodsList = ret_json['data'].get('floorInfoList')[0].get('normalGoodsList')
			promotionFloorGoodsList = ret_json['data'].get('floorInfoList')[0].get('promotionFloorGoodsList')
			for promotionFloorGoods in promotionFloorGoodsList:
				normalGoodsList += promotionFloorGoods.get('promotionGoodsList')
			goods_list = []
			total_amount = 0
			for i in range(len(normalGoodsList)):
				isSelected = normalGoodsList[i].get('isSelected')
				if isSelected:
					goodsName = normalGoodsList[i].get('goodsName')
					spuId = normalGoodsList[i].get('spuId')
					storeId = normalGoodsList[i].get('storeId')
					quantity = normalGoodsList[i].get('quantity')
					price = normalGoodsList[i].get('price')
					goods_list.append({
						"spuId": spuId,
						"storeId": storeId,
						"isSelected": 'true',
						"quantity": quantity,
					})
					print(f'[{i}] {goodsName} {int(price) / 100}元 * {quantity}')
					total_amount += quantity * int(price) / 100
			print(f'--- 共{len(goods_list)}件商品 总价{total_amount}元\n')
			return RET_CODE.SUCCESS, goods_list
		elif ret_json['code'] == 'LIMITED':
			return RET_CODE.LIMITED, None
		else:
			print(f"--- [Error] {ret_json['code']} {ret_json['msg']}")
			return RET_CODE.UNKNOWN_ERROR, None
	except Exception as e:
		print(f"--- [Exception] {str(e)}")
		return RET_CODE.EXCEPTION, None

def GetCapacityData(store_selected):
	print(f'- 获取可用配送时间 {CurrentTime()} -')
	url = public_url + '/api/v1/sams/delivery/portal/getCapacityData'
	try:
		headers = public_headers.copy()
		headers.update({ "Content-Type": 'application/json' })
		date_list = [(datetime.datetime.now() + datetime.timedelta(days = i)).strftime('%Y-%m-%d') for i in range(7)]
		data = {
			"perDateList": date_list,
			"storeDeliveryTemplateId": store_selected.get('storeDeliveryTemplateId'),
		}
		ret = requests.post(url = url, headers = headers, data = json.dumps(data), timeout = TIMEOUT_DURATION)
		ret_json = json.loads(ret.text)
		if ret_json['success']:
			status = ret_json['data'].get('capcityResponseList')[0].get('dateISFull')
			capcitytime_list = ret_json['data'].get('capcityResponseList')[0].get('list')
			for capcitytime in capcitytime_list:
				if not capcitytime.get('timeISFull'):
					startRealTime = capcitytime.get('startRealTime')
					endRealTime = capcitytime.get('endRealTime')
					print(f"--- 配送时间 {FormatTime(startRealTime)} - {FormatTime(endRealTime)} 可用")
					return RET_CODE.SUCCESS, startRealTime, endRealTime
			return RET_CODE.NO_DELIVERY_TIME, 0, 0
		elif ret_json['code'] == 'LIMITED':
			return RET_CODE.LIMITED, 0, 0
		else:
			print(f"--- [Error] {ret_json['code']} {ret_json['msg']}")
			return RET_CODE.UNKNOWN_ERROR, 0, 0
	except Exception as e:
		print(f"--- [Exception] {str(e)}")
		return RET_CODE.EXCEPTION, 0, 0

def CommitPay(address_selected, store_selected, goods_list, personal_info, deliverStartTime, deliverEndTime):
	print(f'- 尝试提交订单 {CurrentTime()} -')
	url = public_url + '/api/v1/sams/trade/settlement/commitPay'
	try:
		headers = public_headers.copy()
		headers.update({ "Content-Type": 'application/json' })
		data = {
			"goodsList": goods_list,
			"invoiceInfo": {},
			"cartDeliveryType": DELIVERY_TYPE, "floorId": 1, "amount": 10000, "purchaserName": "",
			"settleDeliveryInfo": {"expectArrivalTime": deliverStartTime, "expectArrivalEndTime": deliverEndTime,
									"deliveryType": 0}, "tradeType": "APP", "purchaserId": "", "payType": 0,
			"currency": "CNY", "channel": "wechat", "shortageId": 1, "isSelfPickup": 0, "orderType": 0,
			"uid": personal_info.get("uid"), "appId": "wx57364320cb03dfba", "addressId": address_selected.get('addressId'),
			"deliveryInfoVO": {"storeDeliveryTemplateId": store_selected.get('storeDeliveryTemplateId'),
								"deliveryModeId": store_selected.get('deliveryModeId'),
								"storeType": store_selected.get('storeType')}, "remark": "",
			"storeInfo": {"storeId": store_selected.get("storeId"), "storeType": store_selected.get('storeType'),
							"areaBlockId": store_selected.get('areaBlockId')},
			"shortageDesc": "其他商品继续配送（缺货商品直接退款）", "payMethodId": "1486659732"
		}
		
		ret = requests.post(url = url, headers = headers, data = json.dumps(data), timeout = TIMEOUT_DURATION)
		ret_json = json.loads(ret.text)
		if ret_json['success']:
			print('--- 订单成功加入待支付里了，快去付款吧')
			WeComNotify(f'--- {CurrentTime()} 山姆订单成功加入待支付列表，快去付款吧')
			return RET_CODE.SUCCESS
		elif ret_json['code'] == 'LIMITED':
			return RET_CODE.LIMITED
		elif ret_json['code'] == 'NOT_DELIVERY_CAPACITY_ERROR':
			return RET_CODE.NOT_DELIVERY_CAPACITY_ERROR
		elif ret_json['code'] == 'DECREASE_CAPACITY_COUNT_ERROR':
			return RET_CODE.DECREASE_CAPACITY_COUNT_ERROR
		else:
			print(f"--- [Error] {ret_json['code']} {ret_json['msg']}")
			return RET_CODE.UNKNOWN_ERROR
	except Exception as e:
		print(f"--- [Exception] {str(e)}")
		return RET_CODE.EXCEPTION

class STATE_CODE(IntEnum):
	GET_ADDRESS_LIST = 0,
	SELECT_ADDRESS = 1,
	GET_STORE_LIST = 2,
	SELECT_STORE = 3,
	GET_PERSONAL_INFO = 4,
	SAVE_DELIVERY_ADDRESS = 5,
	GET_USER_CART = 6,
	GET_CAPACITY_DATA = 7,
	COMMIT_PAY = 8,
	FINISHED = 9,

# Main Func
if __name__ == '__main__':
	state = STATE_CODE.GET_ADDRESS_LIST
	refresh_cart_count = 0
	while state != STATE_CODE.FINISHED:
		if state == STATE_CODE.GET_ADDRESS_LIST:
			ret_code, address_list = GetAddressList()
		elif state == STATE_CODE.SELECT_ADDRESS:
			ret_code, address_selected = SelectAddress(address_list)
		elif state == STATE_CODE.GET_STORE_LIST:
			ret_code, store_list = GetStoreList()
		elif state == STATE_CODE.SELECT_STORE:
			ret_code, store_selected = SelectStore(store_list)
		elif state == STATE_CODE.GET_PERSONAL_INFO:
			ret_code, personal_info = GetPersonalCenterInfo()
		elif state == STATE_CODE.SAVE_DELIVERY_ADDRESS:
			ret_code = SaveDeliveryAddress(address_selected, personal_info)
		elif state == STATE_CODE.GET_USER_CART:
			refresh_cart_count = 0
			ret_code, goods_list = GetUserCart(personal_info, store_list)
		elif state == STATE_CODE.GET_CAPACITY_DATA:
			if CONST_START_TIME != "" and CONST_END_TIME != "":
				deliverStartTime = UnixTime(CONST_START_TIME)
				deliverEndTime = UnixTime(CONST_END_TIME)
				ret_code = RET_CODE.SUCCESS
			else:
				ret_code, deliverStartTime, deliverEndTime = GetCapacityData(store_selected)
		elif state == STATE_CODE.COMMIT_PAY:
			ret_code = CommitPay(address_selected, store_selected, goods_list, personal_info, deliverStartTime, deliverEndTime)
			
		if ret_code == RET_CODE.SUCCESS:
			state += 1
		elif ret_code == RET_CODE.LIMITED:
			time.sleep(LIMIT_RETRY_TIME)
			print(f"--- [LIMITED] 服务器繁忙 {LIMIT_RETRY_TIME}s后重试\n")
		elif ret_code == RET_CODE.NO_DELIVERY_TIME:
			refresh_cart_count += 1
			if refresh_cart_count == REFRESH_CART_TIME:
				print(f"--- [NO_DELIVERY_TIME] 重新刷新购物车\n")
				state = STATE_CODE.GET_USER_CART
			else:
				print(f"--- [NO_DELIVERY_TIME] 无可用配送时间 {RETRY_TIME}s后重试\n")
			time.sleep(RETRY_TIME)
		elif ret_code == RET_CODE.NOT_DELIVERY_CAPACITY_ERROR:
			print(f"--- [NOT_DELIVERY_CAPACITY_ERROR] 当前配送时间段已约满 {RETRY_TIME}s后重试\n")
			time.sleep(RETRY_TIME)
		elif ret_code == RET_CODE.DECREASE_CAPACITY_COUNT_ERROR:
			print(f"--- [DECREASE_CAPACITY_COUNT_ERROR] 扣减运力失败 {RETRY_TIME}s后重试\n")
			time.sleep(RETRY_TIME)
		else:
			if state >= STATE_CODE.GET_USER_CART:
				time.sleep(RETRY_TIME)
				state = STATE_CODE.GET_USER_CART
			else:
				state = STATE_CODE.GET_ADDRESS_LIST
				