#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "config.h"

int config_load(const char *path, struct config *cfg) {
    FILE *f = fopen(path, "r");
    if (!f) return -1;

    char line[256];
    while (fgets(line, sizeof line, f)) {
        char key[64], value[192];
        if (sscanf(line, "%63[^=]=%191[^\n]", key, value) != 2) continue;
        if (strcmp(key, "port") == 0) cfg->port = atoi(value);
    }

    fclose(f);
    return 0;
}
