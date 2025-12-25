void free (void* ptr);
void* malloc (unsigned long size);

void *_alloca(unsigned long size);  


int main() {

}

void bar(char* p, int b) {
    
    char* a = (char*)malloc(42);
    
    
    if ( b ) {
        free(a);
    }
    
    free(a);
        

    for ( int i = 1; i < b; i++ ) {
        char* t = (char*)_alloca(i*10);
    }    
}
