import rclpy
from rclpy.node import Node
from rclpy.executors import MultiThreadedExecutor
from rclpy.callback_groups import MutuallyExclusiveCallbackGroup

from std_msgs.msg import String

from robonomicsinterface import Datalog, Subscriber, SubEvent
from robonomicsinterface.utils import ipfs_32_bytes_to_qm_hash

from robonomics_ros2_interfaces.srv import RobonomicsROS2ReceiveLastDatalog
from robonomics_ros2_pubsub.utils.crypto_utils import create_account


class RobonomicsROS2Receiver(Node):

    def __init__(self):
        """
        Class for creating node, that subscribe to the topic, get address from there and
        receive the last datalog from Robonomics
        """
        super().__init__('robonomics_ros2_receiver')

        self.account = create_account()
        self.account_address = self.account.get_address()
        self.datalog = Datalog(self.account)
        self.get_logger().info('My address is %s' % self.account_address)

        # Callback group for allowing parallel running
        receive_datalog_callback_group = MutuallyExclusiveCallbackGroup()

        # Create service for receiving last datalog from specified address
        self.datalog = Datalog(self.account)
        self.srv_receive_last_datalog = self.create_service(
            RobonomicsROS2ReceiveLastDatalog,
            'robonomics/receive_last_datalog',
            self.receive_last_datalog_callback,
            callback_group=receive_datalog_callback_group,
        )

        # Publisher of datalog content for received address
        self.datalog_publisher = self.create_publisher(
            String,
            'robonomics/datalog',
            10,
            callback_group=receive_datalog_callback_group,
        )

        # Create subscription of launches for Robonomics node account itself
        self.robonomics_launch_subscriber = Subscriber(
            self.account,
            SubEvent.NewLaunch,
            addr=self.account_address,
            subscription_handler=self.launch_receiver_callback,
        )

        # Publisher of launch param
        self.launch_publisher = self.create_publisher(
            String,
            'robonomics/launch_param',
            10
        )

    def receive_last_datalog_callback(self, request, response):
        """
        Receive last datalog from specified address
        :param request: string with address
        :param response: result message
        :return: response
        """
        datalog_msg = String()
        datalog_msg.data = str(self.datalog.get_item(request.address))
        self.datalog_publisher.publish(datalog_msg)
        response.result = 'Received datalog and published it to topic'
        return response

    def launch_receiver_callback(self, raw_data):
        """
        Method for publish launch param from Robonomics subscription
        :param raw_data: tuple[3]
        :return: None
        """
        launching_account_address = raw_data[0]
        launch_param_msg = String()
        launch_param_msg.data = ipfs_32_bytes_to_qm_hash(raw_data[2])
        self.get_logger().info("Getting launch from %s with param: %s" % (
            launching_account_address,
            launch_param_msg.data)
                               )
        self.launch_publisher.publish(launch_param_msg)

    def __enter__(self):
        """
        Enter the object runtime context
        :return: object itself
        """
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        Exit the object runtime context
        :param exc_type: exception that caused the context to be exited
        :param exc_val: exception value
        :param exc_tb: exception traceback
        :return: None
        """
        self.robonomics_launch_subscriber.cancel()


def main(args=None):
    rclpy.init(args=args)

    executor = MultiThreadedExecutor()

    with RobonomicsROS2Receiver() as robonomics_ros2_receiver:
        try:
            executor.add_node(robonomics_ros2_receiver)
            executor.spin()
        except KeyboardInterrupt:
            robonomics_ros2_receiver.get_logger().warn("Killing the Robonomics receiver node...")
            executor.remove_node(robonomics_ros2_receiver)


if __name__ == '__main__':
    main()
