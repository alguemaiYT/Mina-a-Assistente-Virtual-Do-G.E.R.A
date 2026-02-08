#!/bin/bash
# Build script for C extensions (STT and API communication modules)

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}Building C Extensions for Mina${NC}"
echo "========================================"

# Detect OS
OS="$(uname -s)"
case "${OS}" in
    Linux*)     MACHINE=Linux;;
    Darwin*)    MACHINE=Mac;;
    CYGWIN*)    MACHINE=Cygwin;;
    MINGW*)     MACHINE=MinGw;;
    *)          MACHINE="UNKNOWN:${OS}"
esac

echo "Detected OS: ${MACHINE}"

# Check for required tools
echo ""
echo "Checking for required build tools..."

if ! command -v gcc &> /dev/null; then
    echo -e "${RED}Error: gcc not found. Please install gcc.${NC}"
    exit 1
fi
echo -e "${GREEN}✓ gcc found${NC}"

# Check for portaudio
if [ "${MACHINE}" == "Linux" ]; then
    if ! pkg-config --exists portaudio-2.0; then
        echo -e "${YELLOW}Warning: portaudio not found via pkg-config${NC}"
        echo "Install with: sudo apt-get install portaudio19-dev"
    else
        echo -e "${GREEN}✓ portaudio found${NC}"
    fi
elif [ "${MACHINE}" == "Mac" ]; then
    if ! brew list portaudio &> /dev/null; then
        echo -e "${YELLOW}Warning: portaudio not found via brew${NC}"
        echo "Install with: brew install portaudio"
    else
        echo -e "${GREEN}✓ portaudio found${NC}"
    fi
fi

# Check for curl
if ! pkg-config --exists libcurl 2>/dev/null && ! command -v curl-config &> /dev/null; then
    echo -e "${YELLOW}Warning: libcurl development files not found${NC}"
    if [ "${MACHINE}" == "Linux" ]; then
        echo "Install with: sudo apt-get install libcurl4-openssl-dev"
    elif [ "${MACHINE}" == "Mac" ]; then
        echo "curl should be available by default on macOS"
    fi
else
    echo -e "${GREEN}✓ libcurl found${NC}"
fi

# Create output directories
echo ""
echo "Creating output directories..."
mkdir -p libs/stt
mkdir -p libs/apicomm

# Build flags based on OS
if [ "${MACHINE}" == "Mac" ]; then
    SHARED_FLAG="-dynamiclib"
    STT_OUTPUT="libs/stt/libstt.dylib"
    APICOMM_OUTPUT="libs/apicomm/libapicomm.dylib"
else
    SHARED_FLAG="-shared"
    STT_OUTPUT="libs/stt/libstt.so"
    APICOMM_OUTPUT="libs/apicomm/libapicomm.so"
fi

# Build STT library
echo ""
echo "Building STT library..."
if [ -f "stt.c" ]; then
    gcc ${SHARED_FLAG} -fPIC stt.c -o ${STT_OUTPUT} -lportaudio -lcurl
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ STT library built successfully: ${STT_OUTPUT}${NC}"
    else
        echo -e "${RED}✗ Failed to build STT library${NC}"
        exit 1
    fi
else
    echo -e "${YELLOW}Warning: stt.c not found, skipping STT build${NC}"
fi

# Build API communication library
echo ""
echo "Building API communication library..."
if [ -f "apicomm.c" ]; then
    gcc ${SHARED_FLAG} -fPIC apicomm.c -o ${APICOMM_OUTPUT} -lcurl
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ API communication library built successfully: ${APICOMM_OUTPUT}${NC}"
    else
        echo -e "${RED}✗ Failed to build API communication library${NC}"
        exit 1
    fi
else
    echo -e "${YELLOW}Warning: apicomm.c not found, skipping API communication build${NC}"
fi

# Set library path hint
echo ""
echo "Build complete!"
echo ""
echo "Note: If you encounter library loading issues, set the following environment variables:"
if [ "${MACHINE}" == "Mac" ]; then
    echo "  export DYLD_LIBRARY_PATH=\$DYLD_LIBRARY_PATH:\$(pwd)/libs/stt:\$(pwd)/libs/apicomm"
else
    echo "  export LD_LIBRARY_PATH=\$LD_LIBRARY_PATH:\$(pwd)/libs/stt:\$(pwd)/libs/apicomm"
fi
echo ""
echo "You can now run the application with: python main_gui.py"
