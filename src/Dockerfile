FROM public.ecr.aws/lambda/python:3.11

# 1. Install C and C++ compilers and build tools
RUN yum install -y gcc gcc-c++ make tar gzip

# 2. Copy the local TA-Lib source archive into the container's temporary directory
COPY ta-lib-0.4.0-src.tar.gz /tmp/

# 3. Extract and compile the TA-Lib C-Library from the local copy
RUN cd /tmp && \
    tar -zxf ta-lib-0.4.0-src.tar.gz && \
    cd ta-lib && \
    ./configure --prefix=/usr && \
    make && \
    make install

# 4. Copy your project files and ALL Python scripts into the container
COPY requirements.txt .
COPY *.py .

# 5. Pre-install the exact version of Numpy needed for the Lambda OS
RUN pip install numpy==1.26.4

# 6. Install the rest of the packages, forcing them to use the Numpy we just installed
RUN pip install --no-build-isolation -r requirements.txt

# 7. Set the default command (can be overridden by Terraform)
CMD ["ingestor.handler"]