from kafka_producer import SimpleKafkaProducer
from config_loader import ConfigLoader
from datetime import datetime
import subprocess
import json


def validate_output(output_line):
    """
    프로세스 출력을 검사하는 함수

    Args:
        output_line (str): 검사할 출력 라인

    Returns:
        tuple: (유효 여부, 파싱된 데이터) - 유효하면 (True, data), 아니면 (False, None)

    검사 로직:
    1. JSON 형식인지 확인
    2. "eventType" 항목이 존재하는지 확인
    """
    try:
        # 1. JSON 형식인지 확인
        data = json.loads(output_line)

        # 2. "eventType" 항목이 존재하는지 확인
        if "eventType" in data:
            return True, data
        else:
            return False, None

    except json.JSONDecodeError:
        # JSON 파싱 실패
        return False, None
    except Exception:
        # 기타 오류
        return False, None

def run_process_and_send(process_path, producer):
    """
    지정된 경로의 프로세스를 실행하고 콘솔 출력을 읽어 Kafka로 전송

    Args:
        process_path (str): 실행할 프로세스의 경로
        producer: Kafka Producer 인스턴스
    """
    try:
        # 프로세스 실행 (stdout, stderr 캡처)
        process = subprocess.Popen(
            process_path,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            universal_newlines=True
        )

        print(f'프로세스 실행 중: {process_path}')

        # 실시간으로 출력 읽기
        for line in process.stdout:
            line = line.rstrip('\n')

            # 출력 형식 검사
            is_valid, data = validate_output(line)
            if is_valid:
                # eventType에 따라 토픽 결정
                topic = data.get('eventType')

                producer.send_one(topic, line)
                print(f'✓ 전송됨 [{topic}]: {line[:100]}...')

        # 프로세스 종료 대기
        process.wait()

        # stderr 출력 확인
        stderr_output = process.stderr.read()
        if stderr_output:
            print(f'stderr: {stderr_output}')

        return process.returncode

    except FileNotFoundError:
        print(f'오류: 프로세스를 찾을 수 없습니다 - {process_path}')
        return -1
    except Exception as e:
        print(f'프로세스 실행 오류: {e}')
        return -1


def main():
    """프로세스 출력을 Kafka로 전송하는 예제"""

    # 설정 파일 로드
    config = ConfigLoader()

    # Kafka 브로커 주소 설정
    brokers = config.get_kafka_brokers()

    # Producer 인스턴스 생성
    client_id = config.get_client_id()
    producer = SimpleKafkaProducer(brokers, client_id=client_id)

    # 실행할 프로세스 경로 설정
    process_path = config.get_process_path()

    if not process_path:
        print('오류: config.conf에 process_path가 설정되지 않았습니다.')
        return

    try:
        # Kafka 서버에 연결
        producer.connect()

        # 프로세스 실행 및 출력 전송
        return_code = run_process_and_send(process_path, producer)

        print(f'프로세스 종료 코드: {return_code}')

    except Exception as e:
        print(f'오류 발생: {e}')

    finally:
        # 연결 종료
        producer.disconnect()


if __name__ == '__main__':
    main()
