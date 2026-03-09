.PHONY: all clean install-deps compile

CC := gcc
CFLAGS := -O2 -march=native -Wall -Wextra

all: install-deps compile

install-deps:
@echo 'Installing dependencies...'
apt-get update
apt-get install -y libcjson-dev libcurl4-openssl-dev

compile: apicomm

apicomm: apicomm.c
@echo 'Compiling apicomm...'
gcc -O2 -march=native -Wall -Wextra -o apicomm apicomm.c -lcurl -lcjson
@echo 'SUCCESS: apicomm compiled'
ls -lh apicomm

clean:
@echo 'Cleaning up...'
rm -f apicomm stt *.o
@echo 'Clean complete'
