// ADL - Argument Dependent Lookup
//       or Koenig Lookup

#include <iostream>
#include <boost/static_assert.hpp>
#include <boost/type_traits.hpp>
#include <boost/lexical_cast.hpp>
#include <cassert>
#include <typeinfo>

namespace ADL
{

template <typename T>
void sample(T p)
{
    foo(p);
    typename T::value_type x;
}

} // end ADL


template <typename T>
struct ValueWrapper
{
    typedef T value_type;
    value_type value;
};

void foo(ValueWrapper<int> p)
{
    std::cout << "Int: " << p.value << std::endl;
    // double parenthesis!
    BOOST_STATIC_ASSERT((boost::is_same< ValueWrapper<int>::value_type, int>::value));
}

void foo(ValueWrapper<float> p)
{
    std::cout << "Float: " << p.value << std::endl;
    BOOST_STATIC_ASSERT((boost::is_same< ValueWrapper<float>::value_type, float>::value));
}

namespace Chapter65 { namespace Sample3 {

template <typename T>
struct S3Traits
{
    typedef T value_type;
    static value_type foo(T p) { return p;}
};

template<typename T>
typename S3Traits<T>::value_type sample3( T t ) {
  return S3Traits<T>::foo( t ); // S3Traits<>::foo is a point of customization
  // another example: providing a point of custom-ization to look up a type
  // (usually via typedef)
}                                     

} /* Chapter 65 */ } /* Sample3 */ 

namespace Chapter65 { namespace Sample3 {
    template <>
    struct S3Traits<double>
    {
        typedef std::string value_type;
        static std::string foo(double p) 
        { 
            return boost::lexical_cast<std::string>(p); 
        }
    };
} /* Chapter 65 */ } /* Sample3 */


namespace Chapter65 { namespace Sample4 {

    namespace Detail
    {
        template <typename T>
        T foo(T p) {
            return p;
        }
    } /* end of Detail */

    template<typename T>
    T sample4( T t ) 
    {
        return Detail::foo( t ); 
        // or 
        //using namespace Detail;
        //return (foo)(t);
    }
} /* Chapter 65 */ } /* Sample4 */

namespace Chapter65 { namespace Sample4 { namespace Detail {
    std::string foo(std::string p) 
    {
        return "I'm invoked";
    }
} /* Chapter 65 */ } /* Sample4 */ } /* Detail */

namespace Koenig
{
    class T {};
    void f_Koenig(T) {}
}

int main()
{
    ADL::sample(ValueWrapper<int>());
    ADL::sample(ValueWrapper<float>());

    assert(Chapter65::Sample3::sample3(5) == 5);
    assert(typeid(Chapter65::Sample3::sample3(5.1)) == typeid(std::string));
    assert(typeid(Chapter65::Sample3::sample3(float(5.1))) == typeid(float));

    assert(Chapter65::Sample4::sample4(5) == 5);
    std::string fooStr("Foo");
    std::string s = Chapter65::Sample4::sample4(fooStr);
    assert(Chapter65::Sample4::sample4(fooStr) == fooStr);
    // specialization does not work
    // assert(Chapter65::Sample4::sample4(std::string("Foo")) == std::string("I'm invoked"));
    //

    // good Koenig Lookup example
    Koenig::T param;
    f_Koenig(param); // strange
}
