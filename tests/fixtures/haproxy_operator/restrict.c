/* Test-only inherited filesystem/network denial; no namespace/root privilege. */
#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <linux/audit.h>
#include <linux/filter.h>
#include <linux/landlock.h>
#include <linux/seccomp.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <sys/prctl.h>
#include <sys/syscall.h>
#include <unistd.h>

static void fail(const char *operation) { perror(operation); exit(125); }
static void permit(int ruleset, const char *path, uint64_t rights) {
    int fd = open(path, O_PATH | O_CLOEXEC);
    if (fd < 0) fail(path);
    struct landlock_path_beneath_attr rule = {.allowed_access=rights, .parent_fd=fd};
    if (syscall(SYS_landlock_add_rule,ruleset,LANDLOCK_RULE_PATH_BENEATH,&rule,0)) fail("landlock rule");
    close(fd);
}
#define DENY(call) BPF_JUMP(BPF_JMP|BPF_JEQ|BPF_K,(call),0,1), BPF_STMT(BPF_RET|BPF_K,SECCOMP_RET_ERRNO|EPERM)
int main(int argc, char **argv) {
    if (argc < 4) return 125;
    int abi=syscall(SYS_landlock_create_ruleset,NULL,0,LANDLOCK_CREATE_RULESET_VERSION);
    if (abi < 3) fail("Landlock ABI >= 3 required");
    uint64_t all=(1ULL<<15)-1;
    uint64_t read=LANDLOCK_ACCESS_FS_READ_FILE|LANDLOCK_ACCESS_FS_READ_DIR|LANDLOCK_ACCESS_FS_EXECUTE;
    struct landlock_ruleset_attr config={.handled_access_fs=all};
    int ruleset=syscall(SYS_landlock_create_ruleset,&config,sizeof(config),0);
    if (ruleset < 0) fail("landlock create");
    permit(ruleset,argv[1],all);
    permit(ruleset,"/usr/bin",read); permit(ruleset,"/usr/lib",read);
    permit(ruleset,"/lib",read); permit(ruleset,"/lib64",read); permit(ruleset,"/bin",read);
    permit(ruleset,"/etc/ld.so.cache",LANDLOCK_ACCESS_FS_READ_FILE);
    permit(ruleset,"/dev/null",LANDLOCK_ACCESS_FS_READ_FILE|LANDLOCK_ACCESS_FS_WRITE_FILE);
    permit(ruleset,"/dev/urandom",LANDLOCK_ACCESS_FS_READ_FILE);
    permit(ruleset,"/proc/sys/kernel/random/uuid",LANDLOCK_ACCESS_FS_READ_FILE);
    if (prctl(PR_SET_NO_NEW_PRIVS,1,0,0,0)) fail("no new privileges");
    if (syscall(SYS_landlock_restrict_self,ruleset,0)) fail("landlock restrict");
    close(ruleset);
    struct sock_filter filter[]={
      BPF_STMT(BPF_LD|BPF_W|BPF_ABS,offsetof(struct seccomp_data,arch)),
      BPF_JUMP(BPF_JMP|BPF_JEQ|BPF_K,AUDIT_ARCH_X86_64,1,0),
      BPF_STMT(BPF_RET|BPF_K,SECCOMP_RET_KILL_PROCESS),
      BPF_STMT(BPF_LD|BPF_W|BPF_ABS,offsetof(struct seccomp_data,nr)),
      BPF_JUMP(BPF_JMP|BPF_JSET|BPF_K,0x40000000,0,1),
      BPF_STMT(BPF_RET|BPF_K,SECCOMP_RET_ERRNO|EPERM),
      DENY(SYS_socket),DENY(SYS_connect),DENY(SYS_bind),DENY(SYS_listen),
      DENY(SYS_socketpair),DENY(SYS_sendto),DENY(SYS_sendmsg),DENY(SYS_recvmsg),
      BPF_STMT(BPF_RET|BPF_K,SECCOMP_RET_ALLOW)
    };
    struct sock_fprog program={.len=sizeof(filter)/sizeof(filter[0]),.filter=filter};
    if (prctl(PR_SET_SECCOMP,SECCOMP_MODE_FILTER,&program)) fail("seccomp");
    if (chdir(argv[1])) fail("isolated cwd");
    execvp(argv[2],argv+2); fail("isolated exec");
}
