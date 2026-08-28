cd /mnt/c/Users/gun79/darkchoco
# 다른 배포판의 tor 와 안 부딪히게 SocksPort 도 옮깁니다.
grep -q "^SocksPort 9151" /etc/tor/torrc || printf '\nSocksPort 9151\n' >> /etc/tor/torrc
export DARKCHOCO_TOR_PORT=9081
bash scripts/돌릴자리-만들기.sh
