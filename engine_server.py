from engine.sensitive_file_engine import SensitiveFileEngine
from config_loader import ConfigLoader
import time
import signal
import sys


engines = []


def signal_handler(sig, frame):
    """Ctrl+C 처리"""
    print('\n\n프로그램을 종료합니다...')
    for engine in engines:
        engine.stop()
    sys.exit(0)


def main():
    """통합 분석 엔진 서버"""
    global engines

    print("=" * 60)
    print("Integrated Analysis Engine Server")
    print("=" * 60)

    # 설정 파일 로드
    config = ConfigLoader()

    # 민감 파일 탐지 엔진 생성
    sensitive_engine = SensitiveFileEngine()
    engines.append(sensitive_engine)

    # 출력용 정보 가져오기
    kafka_brokers = config.get_kafka_brokers()
    sensitive_input_topics = config.get_sensitive_file_input_topics()
    sensitive_output_topic = config.get_sensitive_file_output_topic()

    print(f"\n설정:")
    print(f"  - Kafka 브로커: {kafka_brokers}")
    print(f"\n실행 중인 엔진:")
    print(f"  1. Sensitive File Detector Engine")
    print(f"     • 입력 토픽: {', '.join(sensitive_input_topics)}")
    print(f"     • 출력 토픽: {sensitive_output_topic}")
    print(f"     • 탐지 대상: SSH 키, 암호화폐 지갑, 브라우저 쿠키 등")

    try:
        # 모든 엔진 시작
        print("\n엔진들을 시작합니다...")
        for engine in engines:
            engine.start()

        print("✓ 모든 엔진이 실행 중입니다.")
        print("\n종료하려면 Ctrl+C를 누르세요.\n")

        # Ctrl+C 핸들러 등록
        signal.signal(signal.SIGINT, signal_handler)

        # 계속 실행
        while True:
            time.sleep(1)

    except Exception as e:
        print(f"\n오류 발생: {e}")
        for engine in engines:
            engine.stop()
        sys.exit(1)


if __name__ == '__main__':
    main()
