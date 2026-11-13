#ifndef CONFIG_H
#define CONFIG_H

struct config {
    int port;
};

int config_load(const char *path, struct config *cfg);

#endif
