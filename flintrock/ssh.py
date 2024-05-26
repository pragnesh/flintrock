import errno
import os
import socket
import subprocess
import tempfile
import time
import logging
from collections import namedtuple

# External modules
from pssh.clients import SSHClient
from pssh.exceptions import AuthenticationException

# Flintrock modules
from .util import get_subprocess_env
from .exceptions import SSHError

SSHKeyPair = namedtuple('KeyPair', ['public', 'private'])


logger = logging.getLogger('flintrock.ssh')


def generate_ssh_key_pair() -> SSHKeyPair:
    """
    Generate an SSH key pair that the cluster can use for intra-cluster
    communication.
    """
    with tempfile.TemporaryDirectory() as tempdir:
        subprocess.check_call(
            [
                'ssh-keygen',
                '-q',
                '-t', 'ed25519',
                '-N', '',
                '-f', os.path.join(tempdir, 'flintrock_ed25519'),
                '-C', 'flintrock',
            ],
            env=get_subprocess_env(),
        )

        with open(file=os.path.join(tempdir, 'flintrock_ed25519')) as private_key_file:
            private_key = private_key_file.read()

        with open(file=os.path.join(tempdir, 'flintrock_ed25519.pub')) as public_key_file:
            public_key = public_key_file.read()

    return namedtuple('KeyPair', ['public', 'private'])(public_key, private_key)


def get_ssh_client(
        *,
        user: str,
        host: str,
        identity_file: str,
        wait: bool=False,
        print_status: bool=None) -> SSHClient:
    """
    Get an SSH client for the provided host, waiting as necessary for SSH to become
    available.
    """
    if print_status is None:
        print_status = wait

    if wait:
        tries = 100
    else:
        # It's greater than 1 as a band-aid for this issue:
        # https://github.com/nchammas/flintrock/issues/198
        tries = 3

    while tries > 0:
        try:
            tries -= 1
            client = SSHClient(host,
                               user=user,
                               pkey=identity_file,
                               timeout=3)
            if print_status:
                logger.info("[{h}] SSH online.".format(h=host))
            break
        except socket.timeout as e:
            logger.debug("[{h}] SSH timeout.".format(h=host))
            time.sleep(5)
        except AuthenticationException as e:
            logger.debug("[{h}] SSH AuthenticationException.".format(h=host))
            time.sleep(5)
    else:
        raise SSHError(
            host=host,
            message="Could not connect via SSH.")

    return client


def ssh_check_output(
        client: SSHClient,
        command: str,
        timeout_seconds: int=None,
):
    """
    Run a command via the provided SSH client and return the output captured
    on stdout.

    Raise an exception if the command returns a non-zero code.
    """
    host_out = client.run_command(
        command,
        use_pty=True,
        timeout=timeout_seconds)

    stdout_output = []
    stderr_output = []
    for line in host_out.stdout:
        stdout_output.append(line)
    for line in host_out.stderr:
        stderr_output.append(line)
    exit_status = host_out.exit_code

    if exit_status:
        raise SSHError(
            host=client.host,
            message=''.join(stdout_output) + ''.join(stderr_output))

    return ''.join(stdout_output)


def ssh(*, user: str, host: str, identity_file: str):
    """
    SSH into a host for interactive use.
    """
    subprocess.call(
        [
            'ssh',
            '-o', 'StrictHostKeyChecking=no',
            '-i', identity_file,
            '{u}@{h}'.format(u=user, h=host),
        ],
        env=get_subprocess_env(),
    )
