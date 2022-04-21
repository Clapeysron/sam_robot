# sam_robot
山姆自动下单机器人

### 安装依赖
```bash
pip install --index-url https://pypi.douban.com/simple/ requests
```

### 需要抓包填入的字段
通过连接手机抓包（Charles / Burp），将以下字段填入sam_robot.py中
```python
DEVICE_ID = ''
AUTHTOKEN = ''
```
### 配置参数
修改sam_robot.py中自定义的参数
```python
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
```

### 企业微信机器人通知
将企业微信的机器人url填入，下单成功后会发消息通知
```python
# 企业微信机器人通知
WECOM_ROBOT_URL = "" # https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=
```