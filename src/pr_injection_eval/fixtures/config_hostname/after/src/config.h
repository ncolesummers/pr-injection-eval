#ifndef CONFIG_H
#define CONFIG_H

struct config {
    int port;
    char hostname[32];
};

int config_load(const char *path, struct config *cfg);

#endif
