#code generator
def generate_code(number=125)->str:
        characters="1234567890abcdefghijklmnopqrst9vwxyzABCDEFGHIJKLMNOPQRSTVWXYZ"
        results=''
        while number>0:
            remainder=number % 62
            results+=characters[remainder]
            number=number//62
        result=results[::-1]
        code=result.rjust(6,"0")
        return code 




    