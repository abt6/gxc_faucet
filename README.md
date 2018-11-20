# gxc_faucet

## server side:
```
cd your_working_dir

git clone git@github.com:zhuliting/gxc_faucet.git

cd gxc_faucet

python clfaucet.py
```

## client side:

you can get 100 tokens each call and max 1000 tokens per day. 
```
curl http://your_server_ip/get_token?<your_account_name>
```
